from datetime import UTC, datetime

from ..database import Database
from ..models import SessionStatus


class SessionNotFoundError(LookupError):
    pass


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, session_id: str, phone_hash: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, phone_hash, status)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET phone_hash = excluded.phone_hash
                """,
                (session_id, phone_hash, SessionStatus.ACTIVE.value),
            )

    def mark_recording_ready(self, session_id: str, duration_seconds: int) -> None:
        received_at = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET status = ?, recording_duration_seconds = ?, recording_received_at = ?
                WHERE id = ?
                """,
                (
                    SessionStatus.RECORDING_READY.value,
                    duration_seconds,
                    received_at,
                    session_id,
                ),
            )
            if cursor.rowcount == 0:
                raise SessionNotFoundError(session_id)

    def mark_ended(self, session_id: str) -> None:
        ended_at = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions SET status = ?, ended_at = ? WHERE id = ?
                """,
                (SessionStatus.ENDED.value, ended_at, session_id),
            )
            if cursor.rowcount == 0:
                raise SessionNotFoundError(session_id)
