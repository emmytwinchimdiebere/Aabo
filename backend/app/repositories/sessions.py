from datetime import UTC, datetime

from ..database import Database
from ..models import LanguageCode, SessionStatus


class SessionNotFoundError(LookupError):
    pass


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, session_id: str, phone_hash: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, phone_hash, status, language)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    phone_hash = excluded.phone_hash,
                    status = excluded.status
                """,
                (
                    session_id,
                    phone_hash,
                    SessionStatus.ACTIVE.value,
                    LanguageCode.ENGLISH.value,
                ),
            )

    def set_language(self, session_id: str, language: LanguageCode) -> None:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE sessions SET language = ? WHERE id = ?",
                (language.value, session_id),
            )
            if cursor.rowcount == 0:
                raise SessionNotFoundError(session_id)

    def get_language(self, session_id: str) -> LanguageCode:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT language FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise SessionNotFoundError(session_id)
        try:
            return LanguageCode(row["language"])
        except (TypeError, ValueError):
            return LanguageCode.ENGLISH

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
