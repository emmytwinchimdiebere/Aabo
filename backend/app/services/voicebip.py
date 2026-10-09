import hashlib
import hmac
import time
from collections.abc import Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

from ..core.config import Settings
from ..models import LanguageCode
from ..repositories.sessions import SessionNotFoundError, SessionRepository
from .aabo_agent import AaboAgent, AgentReply
from .voice_intake import VoiceIntakeService


class InvalidVoicebipSignature(ValueError):
    pass


class VoicebipSignatureVerifier:
    def __init__(
        self,
        *,
        current_secret: str | None,
        previous_secret: str | None = None,
        max_age_seconds: int = 300,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.secrets = tuple(secret for secret in (current_secret, previous_secret) if secret)
        self.max_age_seconds = max_age_seconds
        self.clock = clock

    def verify(
        self,
        raw_body: bytes,
        *,
        timestamp: str,
        signatures: Sequence[str],
    ) -> None:
        if not self.secrets:
            raise InvalidVoicebipSignature("signing_secret_not_configured")
        try:
            request_time = int(timestamp)
        except (TypeError, ValueError) as error:
            raise InvalidVoicebipSignature("invalid_timestamp") from error
        if abs(self.clock() - request_time) > self.max_age_seconds:
            raise InvalidVoicebipSignature("stale_request")

        message = timestamp.encode("ascii") + b"." + raw_body
        for secret in self.secrets:
            digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
            expected = f"sha256={digest}"
            if any(hmac.compare_digest(expected, signature) for signature in signatures):
                return
        raise InvalidVoicebipSignature("invalid_signature")


class VoicebipIntakeService:
    """Maps VoiceBIP lifecycle events and BYOM turns to the intake domain."""

    def __init__(
        self,
        *,
        voice_intake: VoiceIntakeService,
        sessions: SessionRepository,
        agent: AaboAgent,
        settings: Settings,
    ) -> None:
        self.voice_intake = voice_intake
        self.sessions = sessions
        self.agent = agent
        self.settings = settings

    def register_call(self, call_id: str, caller_number: str) -> None:
        self.voice_intake.begin_call(call_id, caller_number)

    def handle_turn(
        self,
        *,
        agent_id: str,
        call_id: str,
        caller_number: str,
        transcription: str,
        messages: Sequence[Mapping[str, object]],
    ) -> AgentReply:
        self._ensure_call(call_id, caller_number)
        return self.agent.handle_turn(
            call_id=call_id,
            transcription=transcription,
            messages=messages,
            language_hint=self._language_for_agent(agent_id),
        )

    def prepare_recording(
        self,
        *,
        call_id: str,
        caller_number: str,
        duration_seconds: int,
        recording_path: str,
    ) -> tuple[str, dict[str, str]] | None:
        self._ensure_call(call_id, caller_number)
        if not recording_path:
            self.voice_intake.end_call(call_id)
            return None
        self.voice_intake.accept_recording(call_id, duration_seconds)
        recording_url = urljoin(f"{self.settings.voicebip_api_base_url}/", recording_path)
        headers = {}
        api_host = urlsplit(self.settings.voicebip_api_base_url).hostname
        recording_host = urlsplit(recording_url).hostname
        if self.settings.voicebip_api_key and recording_host == api_host:
            headers["Authorization"] = f"Bearer {self.settings.voicebip_api_key}"
        return recording_url, headers

    def close_call(self, call_id: str) -> None:
        self.voice_intake.end_call(call_id)

    def _ensure_call(self, call_id: str, caller_number: str) -> None:
        try:
            self.sessions.get_language(call_id)
        except SessionNotFoundError:
            self.register_call(call_id, caller_number)

    def _language_for_agent(self, agent_id: str) -> LanguageCode | None:
        language_agents = {
            self.settings.voicebip_english_agent_id: LanguageCode.ENGLISH,
            self.settings.voicebip_yoruba_agent_id: LanguageCode.YORUBA,
            self.settings.voicebip_hausa_agent_id: LanguageCode.HAUSA,
            self.settings.voicebip_igbo_agent_id: LanguageCode.IGBO,
        }
        return language_agents.get(agent_id)
