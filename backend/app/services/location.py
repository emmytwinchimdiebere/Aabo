import re
from dataclasses import dataclass

POSTCODE_PATTERN = re.compile(
    r"\b(?:\d{6}|[A-Z]{2}\s?\d{2}\s?[A-Z]\d{2}\s?[A-Z]{2}\s?\d{2})\b",
    re.IGNORECASE,
)
LOCATION_PREFIX_PATTERN = re.compile(
    r"^(?:i(?:'m| am)?\s+(?:at|in|near)|my location is|it is at|we are at|"
    r"near|at|in)\s+",
    re.IGNORECASE,
)

SPECIFIC_PLACE_WORDS = {
    "airport",
    "avenue",
    "bridge",
    "building",
    "bus stop",
    "church",
    "close",
    "estate",
    "filling station",
    "hospital",
    "hotel",
    "junction",
    "market",
    "mosque",
    "road",
    "school",
    "street",
    "village",
}

BROAD_AREAS = {
    "abuja",
    "abia",
    "adamawa",
    "akwa ibom",
    "anambra",
    "bauchi",
    "bayelsa",
    "benue",
    "borno",
    "cross river",
    "delta",
    "ebonyi",
    "edo",
    "ekiti",
    "enugu",
    "gombe",
    "imo",
    "jigawa",
    "kaduna",
    "kano",
    "katsina",
    "kebbi",
    "kogi",
    "kwara",
    "lagos",
    "nasarawa",
    "niger",
    "nigeria",
    "ogun",
    "ondo",
    "osun",
    "oyo",
    "plateau",
    "rivers",
    "sokoto",
    "taraba",
    "yobe",
    "zamfara",
}


@dataclass(frozen=True, slots=True)
class LocationCandidate:
    display_name: str
    confidence: float
    source: str
    needs_detail: bool


class SpokenLocationResolver:
    """Turns a caller's words into a location candidate without claiming GPS proof."""

    def resolve(self, utterance: str) -> LocationCandidate:
        cleaned = " ".join(utterance.strip(" .,!?").split())
        cleaned = LOCATION_PREFIX_PATTERN.sub("", cleaned).strip(" .,!?")
        if not cleaned:
            return LocationCandidate("", 0.0, "spoken", True)

        postcode = POSTCODE_PATTERN.search(cleaned)
        if postcode:
            return LocationCandidate(cleaned, 0.95, "caller_postcode", False)

        lowered = cleaned.casefold()
        if lowered in BROAD_AREAS:
            return LocationCandidate(cleaned, 0.35, "spoken_area", True)

        contains_specific_place = any(word in lowered for word in SPECIFIC_PLACE_WORDS)
        word_count = len(cleaned.split())
        if contains_specific_place:
            confidence = 0.82 if word_count >= 2 else 0.65
            return LocationCandidate(cleaned, confidence, "spoken_landmark", False)
        if word_count >= 3:
            return LocationCandidate(cleaned, 0.7, "spoken_address", False)
        return LocationCandidate(cleaned, 0.45, "spoken_area", True)
