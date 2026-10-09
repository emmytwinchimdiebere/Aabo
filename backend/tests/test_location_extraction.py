import httpx
import pytest

from app.models import LanguageCode
from app.services.location_extraction import NatlasLocationExtractor

pytestmark = pytest.mark.anyio


async def test_extracts_spoken_location_without_marking_it_verified():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"house_number":"19","street":"Osumeyi Street",'
                                '"area":"Awada","city":null,"state":"Anambra",'
                                '"landmark":null,"postcode":null,"emergency_type":"medical"}'
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        extractor = NatlasLocationExtractor(
            client,
            base_url="https://natlas.example",
            api_key="secret",
            timeout_seconds=5,
        )
        result = await extractor.extract(
            "Please come to number 19 Osumeyi Street in Awada",
            LanguageCode.IGBO,
        )

    assert result.address == "19, Osumeyi Street, Awada, Anambra"
    assert result.street == "Osumeyi Street"
    assert result.emergency_type == "Medical"


async def test_does_not_invent_missing_location_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"house_number":null,"street":null,"area":null,'
                                '"city":null,"state":null,"landmark":null,'
                                '"postcode":null,"emergency_type":"fire"}'
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        extractor = NatlasLocationExtractor(
            client,
            base_url="https://natlas.example",
            api_key="secret",
            timeout_seconds=5,
        )
        result = await extractor.extract("There is a fire", LanguageCode.ENGLISH)

    assert result.address == ""
    assert result.emergency_type == "Fire"
