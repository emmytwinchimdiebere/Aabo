from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ...core.config import get_settings
from ...core.security import hash_identifier
from ...database import get_database
from ...models import IncidentSummary, LanguageCode, WebIncidentResponse
from ...repositories.incidents import IncidentRepository, WebIncidentDraft
from ...repositories.sessions import SessionRepository
from ...services.audio import SUPPORTED_AUDIO_TYPES

router = APIRouter(prefix="/incidents", tags=["incidents"])

_AUDIO_EXTENSIONS = {
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
}


def _clean_required(value: str, field: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail=f"{field} is required.")
    if len(cleaned) > maximum:
        raise HTTPException(status_code=422, detail=f"{field} is too long.")
    return cleaned


@router.post("/web", response_model=WebIncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_web_incident(
    language: Annotated[LanguageCode, Form()],
    emergency_type: Annotated[str, Form()],
    confirmed_address: Annotated[str, Form()],
    raw_transcript: Annotated[str, Form()],
    confirmed_transcript: Annotated[str, Form()],
    duration_seconds: Annotated[int, Form(ge=0, le=3600)],
    audio: Annotated[UploadFile, File(description="Original caller recording")],
    latitude: Annotated[float | None, Form(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180)] = None,
    training_consent: Annotated[bool, Form()] = False,
) -> WebIncidentResponse:
    settings = get_settings()
    content_type = (audio.content_type or "").split(";", 1)[0].lower()
    if content_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Upload WAV or MP3 audio.")

    content = await audio.read(settings.recording_max_bytes + 1)
    await audio.close()
    if not content:
        raise HTTPException(status_code=422, detail="Audio file is empty.")
    if len(content) > settings.recording_max_bytes:
        raise HTTPException(status_code=413, detail="Audio file exceeds the upload limit.")

    cleaned_type = _clean_required(emergency_type, "Emergency type", 80)
    cleaned_address = _clean_required(confirmed_address, "Confirmed address", 500)
    cleaned_raw = _clean_required(raw_transcript, "Raw transcript", 5000)
    cleaned_confirmed = _clean_required(confirmed_transcript, "Confirmed transcript", 5000)

    session_id = f"web_{uuid4().hex}"
    recording_id = uuid4().hex
    storage_root = settings.recording_storage_path.resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    recording_path = (storage_root / f"{recording_id}{_AUDIO_EXTENSIONS[content_type]}").resolve()
    if storage_root not in recording_path.parents:
        raise HTTPException(status_code=500, detail="Invalid recording path.")
    recording_path.write_bytes(content)

    sessions = SessionRepository(get_database())
    sessions.create(
        session_id,
        hash_identifier(session_id, settings.phone_hash_salt),
    )
    incident_id = IncidentRepository(get_database()).create_from_web(
        WebIncidentDraft(
            session_id=session_id,
            language=language,
            emergency_type=cleaned_type,
            confirmed_address=cleaned_address,
            raw_transcript=cleaned_raw,
            confirmed_transcript=cleaned_confirmed,
            recording_path=recording_path,
            recording_content_type=content_type,
            recording_duration_seconds=duration_seconds,
            latitude=latitude,
            longitude=longitude,
            training_consent=training_consent,
        )
    )
    return WebIncidentResponse(incident_id=incident_id)


@router.get("", response_model=list[IncidentSummary])
def list_incidents() -> list[IncidentSummary]:
    records = IncidentRepository(get_database()).list_recent()
    return [
        IncidentSummary(
            incident_id=str(record["id"]),
            created_at=str(record["created_at"]),
            language=LanguageCode(str(record["language"] or "en")),
            emergency_type=str(record["emergency_type"] or "Unclassified"),
            confirmed_address=str(record["confirmed_address"]),
            raw_transcript=str(record["raw_transcript"]),
            confirmed_transcript=str(record["confirmed_transcript"]),
            latitude=record["gps_lat"],
            longitude=record["gps_lon"],
            duration_seconds=int(record["duration_seconds"]),
            dispatcher_status=str(record["dispatcher_status"]),
            has_recording=bool(record["recording_path"]),
        )
        for record in records
    ]


@router.get("/{incident_id}/recording")
def get_incident_recording(incident_id: str) -> FileResponse:
    recording = IncidentRepository(get_database()).get_recording(incident_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found.")
    path, content_type = recording
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording file is unavailable.")
    return FileResponse(Path(path), media_type=content_type)
