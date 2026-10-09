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
    service: str = "aabo-112-api"
    version: str
    environment: str


class RecordingAcceptedResponse(BaseModel):
    status: str = "accepted"
    session_id: str
    duration_seconds: int = Field(ge=0)


class SessionClosedResponse(BaseModel):
    status: str = "ended"
    session_id: str
