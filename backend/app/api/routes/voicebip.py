import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ...models import ProviderWebhookAck, VoicebipTurnResponse
from ...services.sms import MAX_SMS_BODY_LENGTH
from ...services.voicebip import InvalidVoicebipSignature
from ..dependencies import (
    Pipeline,
    ProviderEvents,
    SmsService,
    VoicebipService,
    VoicebipVerifier,
)

router = APIRouter(prefix="/webhooks/voicebip", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ProviderWebhookAck | VoicebipTurnResponse)
async def receive_voicebip_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    service: VoicebipService,
    verifier: VoicebipVerifier,
    events: ProviderEvents,
    pipeline: Pipeline,
    sms_service: SmsService,
) -> ProviderWebhookAck | VoicebipTurnResponse:
    raw_body = await request.body()
    signatures = tuple(
        value
        for value in (
            request.headers.get("X-Voicebip-Signature"),
            request.headers.get("X-Voicebip-Signature-Previous"),
        )
        if value
    )
    try:
        verifier.verify(
            raw_body,
            timestamp=request.headers.get("X-Voicebip-Timestamp", ""),
            signatures=signatures,
        )
    except InvalidVoicebipSignature as error:
        status_code = 503 if str(error) == "signing_secret_not_configured" else 401
        raise HTTPException(status_code=status_code, detail="Invalid webhook signature") from error

    try:
        body = json.loads(raw_body)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from error
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    event_type = body.get("event_type")
    if isinstance(event_type, str):
        _handle_lifecycle_event(
            body=body,
            event_type=event_type,
            header_event_id=request.headers.get("X-Voicebip-Event-ID", ""),
            service=service,
            events=events,
            pipeline=pipeline,
            sms_service=sms_service,
            background_tasks=background_tasks,
        )
        return ProviderWebhookAck()

    return _handle_byom_turn(body, service)


def _handle_lifecycle_event(
    *,
    body: dict[str, Any],
    event_type: str,
    header_event_id: str,
    service: VoicebipService,
    events: ProviderEvents,
    pipeline: Pipeline,
    sms_service: SmsService,
    background_tasks: BackgroundTasks,
) -> None:
    event_id = str(body.get("event_id") or header_event_id)
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event ID")

    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid event payload")
    call_id = str(payload.get("call_id") or "")
    caller_number = str(payload.get("from_number") or body.get("from") or "")
    if event_type.startswith("call.") and not call_id:
        raise HTTPException(status_code=400, detail="Missing call ID")
    if event_type == "call.initiated" and not caller_number:
        raise HTTPException(status_code=400, detail="Missing caller number")

    duration_seconds = 0
    if event_type == "call.completed":
        try:
            duration_seconds = max(0, int(payload.get("duration_seconds") or 0))
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="Invalid call duration") from error

    sms_report: dict[str, str] | None = None
    if event_type == "message.received" and body.get("channel") == "sms":
        sms_report = _parse_sms_report(body, payload)

    delivery_receipt: tuple[str, str] | None = None
    if event_type == "message.dlr" and body.get("channel") == "sms":
        message_id = str(payload.get("message_id") or "")
        delivery_status = str(payload.get("status") or "")
        if not message_id or not delivery_status:
            raise HTTPException(status_code=400, detail="Invalid SMS delivery receipt")
        delivery_receipt = (message_id, delivery_status)

    if not events.claim(event_id, "voicebip", event_type):
        return

    if event_type == "call.initiated":
        service.register_call(call_id, caller_number)
        logger.info("VoiceBIP call registered", extra={"session_id": call_id})
        return

    if event_type == "call.completed":
        recording_path = _recording_path(body, payload)
        recording = service.prepare_recording(
            call_id=call_id,
            caller_number=caller_number,
            duration_seconds=duration_seconds,
            recording_path=recording_path,
        )
        if recording is not None:
            recording_url, request_headers = recording
            pipeline.prepare(call_id)
            background_tasks.add_task(
                pipeline.process,
                call_id,
                recording_url,
                request_headers,
            )
            service.close_call(call_id)
            logger.info("VoiceBIP recording accepted", extra={"session_id": call_id})
        else:
            logger.warning(
                "VoiceBIP call completed without recording session=%s duration_seconds=%d",
                call_id,
                duration_seconds,
            )
        return

    if sms_report is not None:
        acknowledgement = sms_service.register_report(**sms_report)
        if acknowledgement is not None:
            background_tasks.add_task(sms_service.send_acknowledgement, acknowledgement)
            logger.info(
                "VoiceBIP SMS report accepted",
                extra={"report_id": sms_report["message_id"]},
            )
        return

    if delivery_receipt is not None:
        sms_service.update_delivery_status(*delivery_receipt)


def _recording_path(body: dict[str, Any], payload: dict[str, Any]) -> str:
    for candidate in (
        payload.get("recording_url"),
        payload.get("recordingUrl"),
        body.get("recording_url"),
        body.get("recordingUrl"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    recording = payload.get("recording")
    if isinstance(recording, dict):
        candidate = recording.get("url")
        if isinstance(candidate, str):
            return candidate.strip()
    return ""


def _parse_sms_report(
    body: dict[str, Any], payload: dict[str, Any]
) -> dict[str, str]:
    report = {
        "message_id": str(payload.get("message_id") or ""),
        "agent_id": str(body.get("agent_id") or ""),
        "sender_number": str(body.get("from") or ""),
        "recipient_number": str(body.get("number") or ""),
        "body": str(payload.get("body") or "").strip(),
    }
    if any(not value for value in report.values()):
        raise HTTPException(status_code=400, detail="Invalid SMS report")
    if len(report["body"]) > MAX_SMS_BODY_LENGTH:
        raise HTTPException(status_code=400, detail="SMS report is too long")
    return report


def _handle_byom_turn(
    body: dict[str, Any], service: VoicebipService
) -> VoicebipTurnResponse:
    if body.get("event") == "call.screening":
        return VoicebipTurnResponse(text="", end_call=False)
    if body.get("event") != "turn":
        raise HTTPException(status_code=400, detail="Unsupported VoiceBIP request")

    call_id = str(body.get("call_id") or "")
    agent_id = str(body.get("agent_id") or "")
    caller_number = str(body.get("from_number") or "")
    transcription = str(body.get("transcription") or "")
    messages = body.get("messages")
    if not agent_id or not call_id or not caller_number or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="Invalid BYOM turn")
    result = service.handle_turn(
        agent_id=agent_id,
        call_id=call_id,
        caller_number=caller_number,
        transcription=transcription,
        messages=[message for message in messages if isinstance(message, dict)],
    )
    return VoicebipTurnResponse(text=result.text, end_call=result.end_call)
