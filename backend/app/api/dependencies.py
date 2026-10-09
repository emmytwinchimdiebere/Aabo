from ..core.config import get_settings
from ..database import get_database
from ..repositories.sessions import SessionRepository
from ..services.voice_intake import VoiceIntakeService


def get_voice_intake_service() -> VoiceIntakeService:
    return VoiceIntakeService(
        sessions=SessionRepository(get_database()),
        settings=get_settings(),
    )
