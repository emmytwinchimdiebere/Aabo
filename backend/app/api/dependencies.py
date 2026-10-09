from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request

from ..core.config import get_settings
from ..database import get_database
from ..models import LanguageCode
from ..repositories.agent_conversations import AgentConversationRepository
from ..repositories.incidents import IncidentRepository
from ..repositories.provider_events import ProviderEventRepository
from ..repositories.sessions import SessionRepository
from ..repositories.text_reports import TextReportRepository
from ..repositories.transcripts import TranscriptRepository
from ..services.aabo_agent import AaboAgent
from ..services.agent_tools import CreateEmergencyIncidentTool
from ..services.audio import AudioDownloader
from ..services.location import SpokenLocationResolver
from ..services.location_extraction import NatlasLocationExtractor
from ..services.recording_pipeline import RecordingPipeline
from ..services.sms import VoicebipSmsService
from ..services.transcription import MultilingualTranscriber
from ..services.voice_intake import VoiceIntakeService
from ..services.voicebip import VoicebipIntakeService, VoicebipSignatureVerifier


def get_voice_intake_service() -> VoiceIntakeService:
    return VoiceIntakeService(
        sessions=SessionRepository(get_database()),
        settings=get_settings(),
    )


def get_recording_pipeline(request: Request) -> RecordingPipeline:
    settings = get_settings()
    http_client = request.app.state.http_client
    transcription = get_multilingual_transcriber(request)
    sessions = SessionRepository(get_database())
    voicebip_host = urlsplit(settings.voicebip_api_base_url).hostname
    allowed_hosts = set(settings.recording_allowed_hosts)
    if voicebip_host:
        allowed_hosts.add(voicebip_host)
    return RecordingPipeline(
        audio_downloader=AudioDownloader(
            http_client,
            allowed_hosts=tuple(allowed_hosts),
            max_bytes=settings.recording_max_bytes,
            timeout_seconds=settings.recording_timeout_seconds,
        ),
        transcriber=transcription,
        sessions=sessions,
        transcripts=TranscriptRepository(get_database()),
        incidents=IncidentRepository(get_database()),
        recording_storage_path=settings.recording_storage_path,
    )


def get_multilingual_transcriber(request: Request) -> MultilingualTranscriber:
    settings = get_settings()
    return MultilingualTranscriber(
        request.app.state.http_client,
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
        natlas_gateway_url=settings.natlas_base_url,
        natlas_api_key=settings.natlas_api_key,
    )


def get_location_extractor(request: Request) -> NatlasLocationExtractor:
    settings = get_settings()
    return NatlasLocationExtractor(
        request.app.state.http_client,
        base_url=settings.natlas_base_url,
        api_key=settings.natlas_api_key,
        timeout_seconds=settings.transcription_timeout_seconds,
    )


def get_voicebip_intake_service() -> VoicebipIntakeService:
    settings = get_settings()
    database = get_database()
    sessions = SessionRepository(database)
    agent = AaboAgent(
        sessions=sessions,
        conversations=AgentConversationRepository(database),
        location_resolver=SpokenLocationResolver(),
        create_incident=CreateEmergencyIncidentTool(IncidentRepository(database)),
    )
    return VoicebipIntakeService(
        voice_intake=VoiceIntakeService(sessions=sessions, settings=settings),
        sessions=sessions,
        agent=agent,
        settings=settings,
    )


def get_voicebip_signature_verifier() -> VoicebipSignatureVerifier:
    settings = get_settings()
    return VoicebipSignatureVerifier(
        current_secret=settings.voicebip_signing_secret,
        previous_secret=settings.voicebip_previous_signing_secret,
        max_age_seconds=settings.voicebip_webhook_max_age_seconds,
    )


def get_provider_event_repository() -> ProviderEventRepository:
    return ProviderEventRepository(get_database())


def get_voicebip_sms_service(request: Request) -> VoicebipSmsService:
    return VoicebipSmsService(
        http_client=request.app.state.http_client,
        reports=TextReportRepository(get_database()),
        settings=get_settings(),
    )


VoiceService = Annotated[VoiceIntakeService, Depends(get_voice_intake_service)]
Pipeline = Annotated[RecordingPipeline, Depends(get_recording_pipeline)]
Transcriber = Annotated[MultilingualTranscriber, Depends(get_multilingual_transcriber)]
LocationExtractor = Annotated[NatlasLocationExtractor, Depends(get_location_extractor)]
VoicebipService = Annotated[VoicebipIntakeService, Depends(get_voicebip_intake_service)]
VoicebipVerifier = Annotated[
    VoicebipSignatureVerifier, Depends(get_voicebip_signature_verifier)
]
ProviderEvents = Annotated[ProviderEventRepository, Depends(get_provider_event_repository)]
SmsService = Annotated[VoicebipSmsService, Depends(get_voicebip_sms_service)]
