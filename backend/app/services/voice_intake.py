import hashlib
import hmac
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from ..core.config import Settings
from ..repositories.sessions import SessionRepository


class VoiceIntakeService:
    """Coordinates provider callbacks without exposing provider details to storage."""

    def __init__(self, sessions: SessionRepository, settings: Settings) -> None:
        self.sessions = sessions
        self.settings = settings

    def begin_call(self, session_id: str, caller_number: str) -> str:
        self.sessions.create(session_id, self._hash_phone_number(caller_number))
        return self._voice_response(session_id)

    def accept_recording(self, session_id: str, duration_seconds: int) -> None:
        self.sessions.mark_recording_ready(session_id, duration_seconds)

    def end_call(self, session_id: str) -> None:
        self.sessions.mark_ended(session_id)

    def _hash_phone_number(self, phone_number: str) -> str:
        return hmac.new(
            self.settings.phone_hash_salt.encode("utf-8"),
            phone_number.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _voice_response(self, session_id: str) -> str:
        query = urlencode({"session_id": session_id})
        callback_url = f"{self.settings.base_url}/voice/recording?{query}"

        response = ET.Element("Response")
        greeting = ET.SubElement(response, "Say")
        greeting.text = (
            "Welcome to Aabo 112. Please describe your emergency and location after the tone."
        )
        ET.SubElement(
            response,
            "Record",
            {
                "finishOnKey": "#",
                "maxLength": "30",
                "trimSilence": "true",
                "playBeep": "true",
                "callbackUrl": callback_url,
            },
        )
        acknowledgement = ET.SubElement(response, "Say")
        acknowledgement.text = "Thank you. A dispatcher will review your report."

        return ET.tostring(response, encoding="unicode", xml_declaration=True)
