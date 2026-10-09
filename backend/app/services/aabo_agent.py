import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..models import LanguageCode
from ..repositories.agent_conversations import (
    AgentConversation,
    AgentConversationRepository,
    ConversationPhase,
)
from ..repositories.sessions import SessionRepository
from .agent_tools import CreateEmergencyIncidentTool, CreateIncidentArguments
from .location import LocationCandidate, SpokenLocationResolver

logger = logging.getLogger(__name__)

LANGUAGE_KEYWORDS = {
    LanguageCode.ENGLISH: ("english", "one", "1"),
    LanguageCode.YORUBA: ("yoruba", "two", "2"),
    LanguageCode.HAUSA: ("hausa", "three", "3"),
    LanguageCode.IGBO: ("igbo", "four", "4", "evo"),
}

LANGUAGE_MARKERS = {
    LanguageCode.ENGLISH: (
        "there is",
        "please",
        "please help",
        "help",
        "i am at",
        "we are at",
        "someone",
        "fire",
        "accident",
        "bleeding",
        "hospital",
        "street",
    ),
    LanguageCode.YORUBA: (
        "e jowo",
        "jowo",
        "mo wa",
        "pajawiri",
        "n sele",
        "n jo",
        "oja",
        "opopona",
        "ile iwosan",
        "ijamba",
    ),
    LanguageCode.HAUSA: (
        "don Allah",
        "akwai",
        "ina nan",
        "gaggawa",
        "wuta",
        "hatsari",
        "kasuwa",
        "asibiti",
        "kusa da",
        "yanzu",
    ),
    LanguageCode.IGBO: (
        "biko",
        "a no m",
        "ihe mberede",
        "oku",
        "ahia",
        "okporo uzo",
        "ulo ogwu",
        "ebe a",
        "ugbu a",
        "onye",
    ),
}

LANGUAGE_CLARIFICATION = (
    "Say one for English, two for Yoruba, three for Hausa, or four for Igbo."
)

LOCATION_REQUESTS = {
    LanguageCode.ENGLISH: (
        "I am Aabo, your emergency assistant. First, tell me where you are. "
        "You can say a street, junction, market, school, hospital, landmark, area, "
        "town, or postcode."
    ),
    LanguageCode.YORUBA: (
        "Emi ni Aabo, oluranlowo pajawiri re. Akoko, so ibi ti o wa. "
        "O le so oruko opopona, orita, oja, ile-iwe, ile-iwosan, ami-ona, ilu, "
        "tabi postcode."
    ),
    LanguageCode.HAUSA: (
        "Ni Aabo, mataimakin gaggawa. Da farko, fada min inda kake. "
        "Kana iya fadin titi, mahada, kasuwa, makaranta, asibiti, wata alama, "
        "gari, ko postcode."
    ),
    LanguageCode.IGBO: (
        "Abu m Aabo, onye enyemaka ihe mberede gi. Biko buru uzo gwa m ebe ino. "
        "I nwere ike ikwu okporo uzo, junction, ahia, ulo akwukwo, ulo ogwu, "
        "ebe ama ama, obodo, ma obu postcode."
    ),
}

DETAIL_REQUESTS = {
    LanguageCode.ENGLISH: (
        "I heard {location}, but I need a more exact place. What street, junction, "
        "market, school, hospital, building, or nearby landmark are you at?"
    ),
    LanguageCode.YORUBA: (
        "Mo gbo {location}, sugbon mo nilo ibi to daju sii. Opopona, orita, oja, "
        "ile-iwe, ile-iwosan, ile, tabi ami-ona wo lo wa nitosi?"
    ),
    LanguageCode.HAUSA: (
        "Na ji {location}, amma ina bukatar karin bayani. Wane titi, mahada, kasuwa, "
        "makaranta, asibiti, gini, ko sanannen wuri ne kusa da kai?"
    ),
    LanguageCode.IGBO: (
        "Anurum {location}, mana achoro ebe doro anya karie. Kedu okporo uzo, "
        "junction, ahia, ulo akwukwo, ulo ogwu, ulo, ma obu ebe ama ama di nso?"
    ),
}

CONFIRM_LOCATION = {
    LanguageCode.ENGLISH: "I heard {location}. Is that correct? Say yes or no.",
    LanguageCode.YORUBA: "Mo gbo {location}. Se ibi naa pe? So beeni tabi rara.",
    LanguageCode.HAUSA: "Na ji {location}. Hakan daidai ne? Ka ce eh ko a'a.",
    LanguageCode.IGBO: "Anurum {location}. O bu eziokwu? Kwuo ee ma obu mba.",
}

EMERGENCY_REQUESTS = {
    LanguageCode.ENGLISH: "Location confirmed. Briefly tell me what is happening now.",
    LanguageCode.YORUBA: "A ti jerisi ibi naa. So ohun ti n sele bayii ni soki.",
    LanguageCode.HAUSA: "An tabbatar da wurin. A takaice, fada min abin da ke faruwa yanzu.",
    LanguageCode.IGBO: "Ekwenyela ebe ahu. Biko gwa m ihe na-eme ugbu a na nkenke.",
}

CONFIRM_EMERGENCY = {
    LanguageCode.ENGLISH: "I heard: {emergency}. Is that correct? Say yes or no.",
    LanguageCode.YORUBA: "Mo gbọ pé: {emergency}. Ṣé ó tọ́? Sọ bẹ́ẹ̀ni tàbí rara.",
    LanguageCode.HAUSA: "Na ji cewa: {emergency}. Hakan daidai ne? Ka ce eh ko a'a.",
    LanguageCode.IGBO: "Anụrụ m: {emergency}. Ọ bụ eziokwu? Kwuo ee ma ọ bụ mba.",
}

COMPLETION_MESSAGES = {
    LanguageCode.ENGLISH: (
        "Your report is with the dispatcher. Stay calm and move to safety if you can."
    ),
    LanguageCode.YORUBA: (
        "A ti gba iroyin re fun oludari. Jowo farabale, lo si ibi aabo ti o ba le."
    ),
    LanguageCode.HAUSA: (
        "An ba jami'in tura agaji rahotonka. Ka kwantar da hankalinka, "
        "ka je wuri mai aminci idan za ka iya."
    ),
    LanguageCode.IGBO: (
        "Onye nhazi anatala akuko gi. Biko wetuo obi, gaa n'ebe nchekwa "
        "ma oburu na i nwere ike."
    ),
}

YES_WORDS = {
    "yes",
    "yeah",
    "correct",
    "right",
    "beeni",
    "eh",
    "ee",
    "eziokwu",
    "that's correct",
    "that is correct",
    "beeni ni",
    "na'am",
    "naam",
    "haka ne",
    "o di mma",
}
NO_WORDS = {
    "no",
    "incorrect",
    "wrong",
    "that's wrong",
    "that is wrong",
    "rara",
    "a'a",
    "ba haka ba",
    "mba",
    "o bughi",
}


@dataclass(frozen=True, slots=True)
class AgentReply:
    text: str
    end_call: bool = False


@dataclass(frozen=True, slots=True)
class LanguageDetection:
    language: LanguageCode
    confidence: float


class AaboAgent:
    """A calm multilingual emergency agent with explicit, auditable tool use."""

    def __init__(
        self,
        *,
        sessions: SessionRepository,
        conversations: AgentConversationRepository,
        location_resolver: SpokenLocationResolver,
        create_incident: CreateEmergencyIncidentTool,
    ) -> None:
        self.sessions = sessions
        self.conversations = conversations
        self.location_resolver = location_resolver
        self.create_incident = create_incident

    def handle_turn(
        self,
        *,
        call_id: str,
        transcription: str,
        messages: Sequence[Mapping[str, object]],
        language_hint: LanguageCode | None = None,
    ) -> AgentReply:
        state = self.conversations.get_or_create(call_id)
        language = self.sessions.get_language(call_id)
        utterance = " ".join(transcription.split()).strip()
        caller_turns = sum(message.get("role") == "caller" for message in messages)
        logger.info(
            "Aabo turn session=%s phase=%s language=%s input_chars=%d caller_turns=%d",
            call_id,
            state.phase.value,
            language.value,
            len(utterance),
            caller_turns,
        )

        if state.phase is ConversationPhase.START:
            selected_language = language_hint or detect_explicit_language(utterance)
            if selected_language is not None:
                self.sessions.set_language(call_id, selected_language)
                self._save(state, phase=ConversationPhase.AWAITING_LOCATION)
                return AgentReply(LOCATION_REQUESTS[selected_language])

            detection = detect_spoken_language(utterance)
            if detection is None or detection.confidence < 0.7:
                if caller_turns >= 2:
                    self.sessions.set_language(call_id, LanguageCode.ENGLISH)
                    self._save(state, phase=ConversationPhase.AWAITING_LOCATION)
                    return AgentReply(LOCATION_REQUESTS[LanguageCode.ENGLISH])
                return AgentReply(LANGUAGE_CLARIFICATION)

            self.sessions.set_language(call_id, detection.language)
            self._save(
                state,
                phase=ConversationPhase.AWAITING_LOCATION,
                emergency_text=utterance or None,
            )
            return AgentReply(LOCATION_REQUESTS[detection.language])

        if state.phase is ConversationPhase.AWAITING_LOCATION:
            candidate = self._location_candidate(state, utterance)
            if candidate.needs_detail:
                attempts = state.location_attempts + 1
                if candidate.display_name and attempts >= 2:
                    self._save_location(state, candidate, attempts=attempts)
                    return AgentReply(
                        CONFIRM_LOCATION[language].format(location=candidate.display_name)
                    )
                self._save(
                    state,
                    phase=ConversationPhase.AWAITING_LOCATION,
                    location_text=candidate.display_name or state.location_text,
                    location_confidence=candidate.confidence,
                    location_source=candidate.source,
                    location_attempts=attempts,
                )
                location = candidate.display_name or "that area"
                return AgentReply(DETAIL_REQUESTS[language].format(location=location))
            self._save_location(
                state,
                candidate,
                attempts=state.location_attempts + 1,
            )
            return AgentReply(CONFIRM_LOCATION[language].format(location=candidate.display_name))

        if state.phase is ConversationPhase.CONFIRMING_LOCATION:
            if is_negative_response(utterance):
                self.conversations.update(
                    state.session_id,
                    phase=ConversationPhase.AWAITING_LOCATION,
                    emergency_text=state.emergency_text,
                    location_text=None,
                    location_confidence=None,
                    location_source=None,
                    location_attempts=0,
                )
                return AgentReply(LOCATION_REQUESTS[language])
            if not is_positive_response(utterance):
                candidate = self.location_resolver.resolve(utterance)
                if not candidate.needs_detail:
                    self._save_location(state, candidate)
                    return AgentReply(
                        CONFIRM_LOCATION[language].format(location=candidate.display_name)
                    )
                return AgentReply(CONFIRM_LOCATION[language].format(location=state.location_text))
            if state.emergency_text:
                return self._request_emergency_confirmation(
                    state, language, state.emergency_text
                )
            self._save(state, phase=ConversationPhase.AWAITING_EMERGENCY)
            return AgentReply(EMERGENCY_REQUESTS[language])

        if state.phase is ConversationPhase.AWAITING_EMERGENCY:
            if not utterance:
                return AgentReply(EMERGENCY_REQUESTS[language])
            return self._request_emergency_confirmation(state, language, utterance)

        if state.phase is ConversationPhase.CONFIRMING_EMERGENCY:
            if is_positive_response(utterance):
                return self._complete_incident(
                    state,
                    language,
                    state.emergency_text or "Emergency details not confirmed",
                )
            if is_negative_response(utterance):
                self._save(
                    state,
                    phase=ConversationPhase.AWAITING_EMERGENCY,
                    emergency_text="",
                )
                return AgentReply(EMERGENCY_REQUESTS[language])
            if not utterance:
                return AgentReply(
                    CONFIRM_EMERGENCY[language].format(
                        emergency=_spoken_summary(state.emergency_text or "the emergency")
                    )
                )
            return self._request_emergency_confirmation(state, language, utterance)

        return AgentReply(COMPLETION_MESSAGES[language], end_call=True)

    def _request_emergency_confirmation(
        self,
        state: AgentConversation,
        language: LanguageCode,
        emergency_text: str,
    ) -> AgentReply:
        self._save(
            state,
            phase=ConversationPhase.CONFIRMING_EMERGENCY,
            emergency_text=emergency_text,
        )
        return AgentReply(
            CONFIRM_EMERGENCY[language].format(
                emergency=_spoken_summary(emergency_text)
            )
        )

    def _location_candidate(
        self, state: AgentConversation, utterance: str
    ) -> LocationCandidate:
        candidate = self.location_resolver.resolve(utterance)
        previous = (state.location_text or "").strip()
        current = candidate.display_name.strip()
        if not previous or not current or current.casefold() in previous.casefold():
            return candidate
        return self.location_resolver.resolve(f"{previous}, {current}")

    def _save_location(
        self,
        state: AgentConversation,
        candidate: LocationCandidate,
        *,
        attempts: int,
    ) -> None:
        self._save(
            state,
            phase=ConversationPhase.CONFIRMING_LOCATION,
            location_text=candidate.display_name,
            location_confidence=candidate.confidence,
            location_source=candidate.source,
            location_attempts=attempts,
        )

    def _complete_incident(
        self,
        state: AgentConversation,
        language: LanguageCode,
        emergency_text: str,
    ) -> AgentReply:
        self.create_incident.invoke(
            CreateIncidentArguments(
                session_id=state.session_id,
                language=language,
                emergency_text=emergency_text,
                location_text=state.location_text or "Location not confirmed",
                location_confidence=state.location_confidence or 0.0,
                location_source=state.location_source or "unresolved",
            )
        )
        self._save(
            state,
            phase=ConversationPhase.COMPLETE,
            emergency_text=emergency_text,
        )
        return AgentReply(COMPLETION_MESSAGES[language], end_call=True)

    def _save(
        self,
        state: AgentConversation,
        *,
        phase: ConversationPhase,
        emergency_text: str | None = None,
        location_text: str | None = None,
        location_confidence: float | None = None,
        location_source: str | None = None,
        location_attempts: int | None = None,
    ) -> None:
        self.conversations.update(
            state.session_id,
            phase=phase,
            emergency_text=(
                emergency_text if emergency_text is not None else state.emergency_text
            ),
            location_text=(
                location_text if location_text is not None else state.location_text
            ),
            location_confidence=(
                location_confidence
                if location_confidence is not None
                else state.location_confidence
            ),
            location_source=(
                location_source if location_source is not None else state.location_source
            ),
            location_attempts=(
                location_attempts
                if location_attempts is not None
                else state.location_attempts
            ),
        )
        logger.info(
            "Aabo state transition session=%s from=%s to=%s location_attempts=%d",
            state.session_id,
            state.phase.value,
            phase.value,
            location_attempts
            if location_attempts is not None
            else state.location_attempts,
        )


def detect_explicit_language(value: str) -> LanguageCode | None:
    normalized = _normalize(value).strip(" .,!?'\"")
    tokens = set(re.findall(r"[a-z]+|\d+", normalized))
    for language, keywords in LANGUAGE_KEYWORDS.items():
        language_name = keywords[0]
        numeric_aliases = keywords[1:]
        if language_name in normalized or any(alias in tokens for alias in numeric_aliases):
            return language
    return None


def is_positive_response(value: str) -> bool:
    return _is_repeated_response(value, YES_WORDS)


def is_negative_response(value: str) -> bool:
    return _is_repeated_response(value, NO_WORDS)


def _is_repeated_response(value: str, accepted: set[str]) -> bool:
    normalized = _normalize(value).strip(" .,!?'\"")
    if normalized in accepted:
        return True
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?", normalized)
    return bool(tokens) and all(token in accepted for token in tokens)


def detect_spoken_language(value: str) -> LanguageDetection | None:
    normalized = _normalize(value)
    scores = {
        language: sum(marker.casefold() in normalized for marker in markers)
        for language, markers in LANGUAGE_MARKERS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    language, score = ranked[0]
    runner_up = ranked[1][1]
    if score == 0 or score == runner_up:
        return None
    confidence = 0.9 if score >= 2 else 0.75
    return LanguageDetection(language=language, confidence=confidence)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(normalized.split())


def _spoken_summary(value: str, maximum: int = 240) -> str:
    cleaned = " ".join(value.split()).strip(" .,!?")
    if len(cleaned) <= maximum:
        return cleaned
    shortened = cleaned[: maximum - 1].rsplit(" ", 1)[0].rstrip(" .,!?")
    return f"{shortened}…"
