import json
from dataclasses import dataclass
from typing import Any

import httpx

from ..models import LanguageCode

_FIELDS = ("house_number", "street", "area", "city", "state", "landmark", "postcode")
_EMERGENCY_TYPES = {"medical", "fire", "security", "accident", "other"}


class LocationExtractionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractedLocation:
    address: str
    house_number: str | None = None
    street: str | None = None
    area: str | None = None
    city: str | None = None
    state: str | None = None
    landmark: str | None = None
    postcode: str | None = None
    emergency_type: str | None = None


def _optional_text(value: Any, maximum: int = 250) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned[:maximum] or None


def _json_object(content: str) -> dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        raise LocationExtractionError("location_extraction_invalid_response")
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as error:
        raise LocationExtractionError("location_extraction_invalid_response") from error
    if not isinstance(parsed, dict):
        raise LocationExtractionError("location_extraction_invalid_response")
    return parsed


def _display_address(values: dict[str, str | None]) -> str:
    ordered = [
        values.get("house_number"),
        values.get("street"),
        values.get("area"),
        values.get("city"),
        values.get("state"),
        values.get("landmark"),
        values.get("postcode"),
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for value in ordered:
        if value and value.casefold() not in seen:
            unique.append(value)
            seen.add(value.casefold())
    return ", ".join(unique)


class NatlasLocationExtractor:
    """Extracts only spoken address fields; it never marks them as verified."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str | None,
        api_key: str | None,
        timeout_seconds: float,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def extract(self, transcript: str, language: LanguageCode) -> ExtractedLocation:
        if not self.base_url or not self.api_key:
            raise LocationExtractionError("location_extraction_not_configured")

        system_prompt = (
            "You extract emergency location details from a speech transcript. "
            "Return one JSON object only with keys house_number, street, area, city, "
            "state, landmark, postcode, emergency_type. Use null when absent. "
            "emergency_type must be medical, fire, security, accident, or other. "
            "Copy place names exactly as written in the transcript. Never correct, "
            "translate, guess, or invent a location."
        )
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": "NCAIR1/N-ATLaS",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": transcript},
                    ],
                    "language": language.value,
                    "temperature": 0,
                    "max_tokens": 220,
                    "response_format": {"type": "json_object"},
                    "stream": False,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LocationExtractionError("location_extraction_failed") from error

        parsed = _json_object(str(content))
        values = {field: _optional_text(parsed.get(field)) for field in _FIELDS}
        emergency_type = _optional_text(parsed.get("emergency_type"), 20)
        if emergency_type and emergency_type.casefold() not in _EMERGENCY_TYPES:
            emergency_type = None
        if emergency_type:
            emergency_type = emergency_type.capitalize()

        return ExtractedLocation(
            address=_display_address(values),
            emergency_type=emergency_type,
            **values,
        )
