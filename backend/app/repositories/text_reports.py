from datetime import UTC, datetime

from ..database import Database


class TextReportRepository:
    """Persists text-based reports without retaining the sender's phone number."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        report_id: str,
        provider: str,
        channel: str,
        sender_hash: str,
        recipient: str,
        body: str,
        language: str | None = None,
    ) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO text_reports (
                    id, provider, channel, sender_hash, recipient, body, language
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    provider,
                    channel,
                    sender_hash,
                    recipient,
                    body,
                    language,
                ),
            )
            return cursor.rowcount == 1

    def mark_acknowledgement_queued(
        self,
        report_id: str,
        acknowledgement_message_id: str,
        status: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE text_reports SET
                    status = 'acknowledged',
                    acknowledgement_message_id = ?,
                    acknowledgement_status = ?,
                    failure_code = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (acknowledgement_message_id, status, now, report_id),
            )

    def mark_acknowledgement_failed(self, report_id: str, failure_code: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE text_reports SET
                    status = 'acknowledgement_failed',
                    failure_code = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (failure_code, now, report_id),
            )

    def update_delivery_status(self, acknowledgement_message_id: str, status: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE text_reports SET acknowledgement_status = ?, updated_at = ?
                WHERE acknowledgement_message_id = ?
                """,
                (status, now, acknowledgement_message_id),
            )
