from dataclasses import dataclass
from enum import StrEnum

from ..database import Database


class ConversationPhase(StrEnum):
    START = "start"
    AWAITING_LOCATION = "awaiting_location"
    CONFIRMING_LOCATION = "confirming_location"
    AWAITING_EMERGENCY = "awaiting_emergency"
    CONFIRMING_EMERGENCY = "confirming_emergency"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class AgentConversation:
    session_id: str
    phase: ConversationPhase
    emergency_text: str | None
    location_text: str | None
    location_confidence: float | None
    location_source: str | None
    location_attempts: int


class AgentConversationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_or_create(self, session_id: str) -> AgentConversation:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO agent_conversations (session_id, phase)
                VALUES (?, ?)
                """,
                (session_id, ConversationPhase.START.value),
            )
            row = connection.execute(
                """
                SELECT session_id, phase, emergency_text, location_text,
                       location_confidence, location_source, location_attempts
                FROM agent_conversations
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"Unable to create conversation state for {session_id}")
        return AgentConversation(
            session_id=row["session_id"],
            phase=ConversationPhase(row["phase"]),
            emergency_text=row["emergency_text"],
            location_text=row["location_text"],
            location_confidence=row["location_confidence"],
            location_source=row["location_source"],
            location_attempts=row["location_attempts"],
        )

    def update(
        self,
        session_id: str,
        *,
        phase: ConversationPhase,
        emergency_text: str | None = None,
        location_text: str | None = None,
        location_confidence: float | None = None,
        location_source: str | None = None,
        location_attempts: int = 0,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_conversations
                SET phase = ?, emergency_text = ?, location_text = ?,
                    location_confidence = ?, location_source = ?,
                    location_attempts = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (
                    phase.value,
                    emergency_text,
                    location_text,
                    location_confidence,
                    location_source,
                    location_attempts,
                    session_id,
                ),
            )
