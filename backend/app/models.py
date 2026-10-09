from enum import StrEnum

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    ACTIVE = "active"
    RECORDING_READY = "recording_ready"
    ENDED = "ended"


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
