from ..database import Database


class ProviderEventRepository:
    """Claims provider event IDs so at-least-once delivery stays idempotent."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def claim(self, event_id: str, provider: str, event_type: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO provider_events (event_id, provider, event_type)
                VALUES (?, ?, ?)
                """,
                (event_id, provider, event_type),
            )
            return cursor.rowcount == 1
