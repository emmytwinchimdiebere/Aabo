from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ..database import Database
from ..models import LanguageCode


@dataclass(frozen=True, slots=True)
class IncidentDraft:
    session_id: str
    language: LanguageCode
    emergency_text: str
    emergency_type: str
    spoken_location: str
    location_confidence: float
    location_source: str


@dataclass(frozen=True, slots=True)
class WebIncidentDraft:
    session_id: str
    language: LanguageCode
    emergency_type: str
    confirmed_address: str
    raw_transcript: str
    confirmed_transcript: str
    recording_path: Path
    recording_content_type: str
    recording_duration_seconds: int
    latitude: float | None = None
    longitude: float | None = None
    training_consent: bool = False


class IncidentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_from_agent(self, draft: IncidentDraft) -> str:
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM incidents WHERE session_id = ? ORDER BY created_at LIMIT 1",
                (draft.session_id,),
            ).fetchone()
            if existing is not None:
                return str(existing["id"])

            incident_id = f"inc_{uuid4().hex[:16]}"
            connection.execute(
                """
                INSERT INTO incidents (
                    id, session_id, language, emergency_type, spoken_location,
                    location_match, presence_score, risk_level, transcript
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    draft.session_id,
                    draft.language.value,
                    draft.emergency_type,
                    draft.spoken_location,
                    f"caller_confirmed:{draft.location_source}",
                    draft.location_confidence,
                    "high",
                    draft.emergency_text,
                ),
            )
        return incident_id

    def create_from_web(self, draft: WebIncidentDraft) -> str:
        incident_id = f"inc_{uuid4().hex[:16]}"
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    id, session_id, language, emergency_type, gps_lat, gps_lon,
                    formatted_address, spoken_location, location_match,
                    presence_score, risk_level, transcript, original_transcript,
                    recording_path, recording_content_type,
                    recording_duration_seconds, training_consent,
                    training_review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    draft.session_id,
                    draft.language.value,
                    draft.emergency_type,
                    draft.latitude,
                    draft.longitude,
                    draft.confirmed_address,
                    draft.confirmed_address,
                    "caller_confirmed:web",
                    1.0,
                    "high",
                    draft.confirmed_transcript,
                    draft.raw_transcript,
                    str(draft.recording_path),
                    draft.recording_content_type,
                    draft.recording_duration_seconds,
                    int(draft.training_consent),
                    "pending" if draft.training_consent else "not_requested",
                ),
            )
        return incident_id

    def list_transcription_feedback(
        self, review_status: str = "approved"
    ) -> list[dict[str, object]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, language, original_transcript,
                       transcript, recording_path, recording_content_type,
                       training_review_status
                FROM incidents
                WHERE training_consent = 1
                  AND training_review_status = ?
                  AND recording_path IS NOT NULL
                  AND original_transcript IS NOT NULL
                  AND transcript IS NOT NULL
                ORDER BY created_at
                """,
                (review_status,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_training_review_status(self, incident_id: str, review_status: str) -> bool:
        if review_status not in {"approved", "rejected"}:
            raise ValueError("review_status must be approved or rejected")
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE incidents
                SET training_review_status = ?
                WHERE id = ? AND training_consent = 1
                """,
                (review_status, incident_id),
            )
        return cursor.rowcount > 0

    def list_recent(self, limit: int = 50) -> list[dict[str, object]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, language, emergency_type,
                       COALESCE(formatted_address, spoken_location, '') AS confirmed_address,
                       COALESCE(original_transcript, transcript, '') AS raw_transcript,
                       COALESCE(transcript, '') AS confirmed_transcript,
                       gps_lat, gps_lon,
                       COALESCE(recording_duration_seconds, 0) AS duration_seconds,
                       dispatcher_status, recording_path
                FROM incidents
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recording(self, incident_id: str) -> tuple[Path, str] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT recording_path, recording_content_type
                FROM incidents WHERE id = ?
                """,
                (incident_id,),
            ).fetchone()
        if row is None or not row["recording_path"]:
            return None
        return Path(row["recording_path"]), str(row["recording_content_type"] or "audio/wav")

    def attach_recording(
        self,
        session_id: str,
        path: Path,
        content_type: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE incidents SET
                    recording_path = ?,
                    recording_content_type = ?,
                    recording_duration_seconds = COALESCE(
                        recording_duration_seconds,
                        (SELECT recording_duration_seconds FROM sessions WHERE id = ?)
                    )
                WHERE session_id = ?
                """,
                (str(path), content_type, session_id, session_id),
            )
