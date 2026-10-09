from datetime import UTC, datetime

from ..database import Database
from ..models import TranscriptResult, TranscriptStatus


class TranscriptRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def mark_processing(self, session_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO transcripts (session_id, status, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    error_code = NULL,
                    updated_at = excluded.updated_at
                """,
                (session_id, TranscriptStatus.PROCESSING.value, now),
            )

    def save(self, session_id: str, result: TranscriptResult) -> None:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE transcripts SET
                    status = ?, text = ?, language = ?, confidence = ?,
                    provider = ?, model = ?, fallback_used = ?,
                    error_code = NULL, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    TranscriptStatus.COMPLETE.value,
                    result.text,
                    result.language,
                    result.confidence,
                    result.provider,
                    result.model,
                    int(result.fallback_used),
                    now,
                    session_id,
                ),
            )

    def mark_manual_required(self, session_id: str, error_code: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE transcripts SET status = ?, error_code = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    TranscriptStatus.MANUAL_REQUIRED.value,
                    error_code,
                    now,
                    session_id,
                ),
            )
