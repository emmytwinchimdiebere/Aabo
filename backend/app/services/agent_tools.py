import logging
from dataclasses import dataclass

from ..models import LanguageCode
from ..repositories.incidents import IncidentDraft, IncidentRepository

logger = logging.getLogger(__name__)

EMERGENCY_KEYWORDS = {
    "fire": ("fire", "burning", "smoke", "ina", "wuta", "ọkụ"),
    "medical": (
        "bleeding",
        "collapsed",
        "injured",
        "medical",
        "unconscious",
        "farapa",
        "jini",
        "rauni",
        "ọbara",
    ),
    "security": (
        "attack",
        "gun",
        "kidnap",
        "robbery",
        "thief",
        "violence",
        "bindiga",
        "ibọn",
        "mwakpo",
    ),
    "accident": ("accident", "collision", "crash", "hatsari", "ijamba"),
}


@dataclass(frozen=True, slots=True)
class CreateIncidentArguments:
    session_id: str
    language: LanguageCode
    emergency_text: str
    location_text: str
    location_confidence: float
    location_source: str


class CreateEmergencyIncidentTool:
    """Allowlisted tool used by the Aabo agent to persist a dispatcher report."""

    name = "create_emergency_incident"

    def __init__(self, incidents: IncidentRepository) -> None:
        self.incidents = incidents

    def invoke(self, arguments: CreateIncidentArguments) -> str:
        incident_id = self.incidents.create_from_agent(
            IncidentDraft(
                session_id=arguments.session_id,
                language=arguments.language,
                emergency_text=arguments.emergency_text,
                emergency_type=classify_emergency(arguments.emergency_text),
                spoken_location=arguments.location_text,
                location_confidence=arguments.location_confidence,
                location_source=arguments.location_source,
            )
        )
        logger.info(
            "Agent tool invoked",
            extra={
                "tool": self.name,
                "session_id": arguments.session_id,
                "incident_id": incident_id,
            },
        )
        return incident_id


def classify_emergency(text: str) -> str:
    normalized = text.casefold()
    for emergency_type, keywords in EMERGENCY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return emergency_type
    return "other"
