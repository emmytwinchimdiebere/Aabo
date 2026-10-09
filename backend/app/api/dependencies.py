from typing import Annotated

from fastapi import Depends, Request

from ..core.config import get_settings
from ..database import get_database
from ..models import LanguageCode
from ..repositories.sessions import SessionRepository
from ..repositories.transcripts import TranscriptRepository
from ..services.audio import AudioDownloader
from ..services.recording_pipeline import RecordingPipeline
from ..services.transcription import MultilingualTranscriber
from ..services.voice_intake import VoiceIntakeService


def get_voice_intake_service() -> VoiceIntakeService:
    return VoiceIntakeService(
        sessions=SessionRepository(get_database()),
        settings=get_settings(),
    )


def get_recording_pipeline(request: Request) -> RecordingPipeline:
    settings = get_settings()
    http_client = request.app.state.http_client
    transcription = MultilingualTranscriber(
        http_client,
        token=settings.hf_token,
        base_url=settings.hf_inference_base_url,
        natlas_models={
            LanguageCode.ENGLISH: settings.natlas_english_model,
            LanguageCode.YORUBA: settings.natlas_yoruba_model,
            LanguageCode.HAUSA: settings.natlas_hausa_model,
            LanguageCode.IGBO: settings.natlas_igbo_model,
        },
        fallback_model=settings.fallback_asr_model,
        timeout_seconds=settings.transcription_timeout_seconds,
    )
    sessions = SessionRepository(get_database())
    return RecordingPipeline(
        audio_downloader=AudioDownloader(
            http_client,
            allowed_hosts=settings.recording_allowed_hosts,
            max_bytes=settings.recording_max_bytes,
            timeout_seconds=settings.recording_timeout_seconds,
        ),
        transcriber=transcription,
        sessions=sessions,
        transcripts=TranscriptRepository(get_database()),
    )


VoiceService = Annotated[VoiceIntakeService, Depends(get_voice_intake_service)]
Pipeline = Annotated[RecordingPipeline, Depends(get_recording_pipeline)]
