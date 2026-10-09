import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from ..core.config import Settings
from ..core.security import hash_identifier
from ..models import LanguageCode
from ..repositories.sessions import SessionRepository

LANGUAGE_BY_DIGIT = {
    "1": LanguageCode.ENGLISH,
    "2": LanguageCode.YORUBA,
    "3": LanguageCode.HAUSA,
    "4": LanguageCode.IGBO,
}


class VoiceIntakeService:
    """Coordinates provider callbacks without exposing provider details to storage."""

    def __init__(self, sessions: SessionRepository, settings: Settings) -> None:
        self.sessions = sessions
        self.settings = settings

    def begin_call(self, session_id: str, caller_number: str) -> str:
        self.sessions.create(session_id, self._hash_phone_number(caller_number))
        return self._language_prompt_response(session_id)

    def select_language(self, session_id: str, digit: str) -> str:
        language = LANGUAGE_BY_DIGIT.get(digit, LanguageCode.ENGLISH)
        self.sessions.set_language(session_id, language)
        return self._recording_response(session_id, language)

    def accept_recording(self, session_id: str, duration_seconds: int) -> None:
        self.sessions.mark_recording_ready(session_id, duration_seconds)

    def end_call(self, session_id: str) -> None:
        self.sessions.mark_ended(session_id)

    def _hash_phone_number(self, phone_number: str) -> str:
        return hash_identifier(phone_number, self.settings.phone_hash_salt)

    def _language_prompt_response(self, session_id: str) -> str:
        query = urlencode({"session_id": session_id})
        response = ET.Element("Response")
        collect = ET.SubElement(
            response,
            "GetDigits",
            {
                "numDigits": "1",
                "timeout": "6",
                "finishOnKey": "#",
                "callbackUrl": f"{self.settings.base_url}/voice/language?{query}",
            },
        )
        prompt = ET.SubElement(collect, "Say")
        prompt.text = (
            "Welcome to Aabo. For English press 1. For Yoruba press 2. "
            "For Hausa press 3. For Igbo press 4."
        )
        fallback = ET.SubElement(response, "Say")
        fallback.text = "Continuing in English."
        self._append_recording_actions(response, session_id, LanguageCode.ENGLISH)
        return ET.tostring(response, encoding="unicode", xml_declaration=True)

    def _recording_response(self, session_id: str, language: LanguageCode) -> str:
        response = ET.Element("Response")
        self._append_recording_actions(response, session_id, language)
        return ET.tostring(response, encoding="unicode", xml_declaration=True)

    def _append_recording_actions(
        self, response: ET.Element, session_id: str, language: LanguageCode
    ) -> None:
        query = urlencode({"session_id": session_id})
        callback_url = f"{self.settings.base_url}/voice/recording?{query}"
        prompt = ET.SubElement(response, "Say")
        prompt.text = (
            f"{language.name.title()} selected. Please describe your emergency and "
            "location after the tone."
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
