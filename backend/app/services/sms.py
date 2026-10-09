import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from ..core.config import Settings
from ..core.security import hash_identifier
from ..repositories.text_reports import TextReportRepository

logger = logging.getLogger(__name__)
MAX_SMS_BODY_LENGTH = 4_000


class SmsDeliveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SmsAcknowledgement:
    report_id: str
    agent_id: str
    from_number: str
    to_number: str


class VoicebipSmsService:
    """Stores inbound emergency texts and sends a short receipt over VoiceBIP."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        reports: TextReportRepository,
        settings: Settings,
    ) -> None:
        self.http_client = http_client
        self.reports = reports
        self.settings = settings

    def register_report(
        self,
        *,
        message_id: str,
        agent_id: str,
        sender_number: str,
        recipient_number: str,
        body: str,
    ) -> SmsAcknowledgement | None:
        normalized_body = body.strip()
        if not normalized_body or len(normalized_body) > MAX_SMS_BODY_LENGTH:
            raise ValueError("invalid_sms_body")
        created = self.reports.create(
            report_id=message_id,
            provider="voicebip",
            channel="sms",
            sender_hash=hash_identifier(sender_number, self.settings.phone_hash_salt),
            recipient=recipient_number,
            body=normalized_body,
        )
        if not created:
            return None
        return SmsAcknowledgement(
            report_id=message_id,
            agent_id=agent_id,
            from_number=recipient_number,
            to_number=sender_number,
        )

    async def send_acknowledgement(self, acknowledgement: SmsAcknowledgement) -> None:
        try:
            message_id, status = await self._send(acknowledgement)
        except SmsDeliveryError as error:
            self.reports.mark_acknowledgement_failed(acknowledgement.report_id, error.code)
            logger.error(
                "SMS acknowledgement failed",
                extra={"report_id": acknowledgement.report_id, "code": error.code},
            )
            return
        self.reports.mark_acknowledgement_queued(
            acknowledgement.report_id,
            message_id,
            status,
        )
        logger.info(
            "SMS report acknowledged",
            extra={"report_id": acknowledgement.report_id},
        )

    def update_delivery_status(self, message_id: str, status: str) -> None:
        self.reports.update_delivery_status(message_id, status)

    async def _send(self, acknowledgement: SmsAcknowledgement) -> tuple[str, str]:
        if not self.settings.voicebip_api_key:
            raise SmsDeliveryError("voicebip_not_configured")
        try:
            response = await self.http_client.post(
                urljoin(f"{self.settings.voicebip_api_base_url}/", "messages"),
                headers={
                    "Authorization": f"Bearer {self.settings.voicebip_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "agent_id": acknowledgement.agent_id,
                    "channel": "sms",
                    "from_number": acknowledgement.from_number,
                    "to_number": acknowledgement.to_number,
                    "body": self.settings.sms_acknowledgement_text,
                },
                timeout=self.settings.voicebip_request_timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise SmsDeliveryError("voicebip_timeout") from error
        except httpx.HTTPError as error:
            raise SmsDeliveryError("voicebip_request_failed") from error
        if response.status_code not in {200, 201}:
            raise SmsDeliveryError("voicebip_delivery_rejected")
        try:
            payload = response.json()
            message_id = str(payload["message_id"])
            status = str(payload.get("status") or "queued")
        except (KeyError, TypeError, ValueError) as error:
            raise SmsDeliveryError("invalid_voicebip_response") from error
        if not message_id:
            raise SmsDeliveryError("invalid_voicebip_response")
        return message_id, status
