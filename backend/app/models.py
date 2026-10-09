from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    ACTIVE = "active"
    RECORDING_READY = "recording_ready"
    ENDED = "ended"


class LanguageCode(StrEnum):
    ENGLISH = "en"
    YORUBA = "yo"
    HAUSA = "ha"
    IGBO = "ig"


class TranscriptStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True, slots=True)
class DownloadedAudio:
    content: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    text: str
    provider: str
    model: str
    language: str | None = None
    confidence: float | None = None
    fallback_used: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "aabo-api"
    version: str
    environment: str


class RecordingAcceptedResponse(BaseModel):
    status: str = "accepted"
    session_id: str
    duration_seconds: int = Field(ge=0)


class TranscriptionResponse(BaseModel):
    text: str
    language: LanguageCode
    provider: str
    model: str
    fallback_used: bool
    elapsed_ms: int = Field(ge=0)


class LocationExtractionRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=5000)
    language: LanguageCode


class LocationExtractionResponse(BaseModel):
    address: str = ""
    house_number: str | None = None
    street: str | None = None
    area: str | None = None
    city: str | None = None
    state: str | None = None
    landmark: str | None = None
    postcode: str | None = None
    emergency_type: str | None = None
    source: str = "n-atlas"
    verified: bool = False


class WebIncidentResponse(BaseModel):
    incident_id: str
    status: str = "received"


class IncidentSummary(BaseModel):
    incident_id: str
    created_at: str
    language: LanguageCode
    emergency_type: str
    confirmed_address: str
    raw_transcript: str
    confirmed_transcript: str
    latitude: float | None = None
    longitude: float | None = None
    duration_seconds: int = Field(ge=0)
    dispatcher_status: str
    has_recording: bool


class SessionClosedResponse(BaseModel):
    status: str = "ended"
    session_id: str


class ProviderWebhookAck(BaseModel):
    received: bool = True


class VoicebipTurnResponse(BaseModel):
    text: str
    end_call: bool = False
