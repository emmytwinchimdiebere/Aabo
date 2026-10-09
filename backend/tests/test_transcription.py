import httpx
import pytest

from app.models import DownloadedAudio, LanguageCode
from app.services.transcription import (
    HuggingFaceTranscriber,
    MultilingualTranscriber,
    TranscriptionChain,
)

pytestmark = pytest.mark.anyio


def transcriber(client, model: str, provider: str) -> HuggingFaceTranscriber:
    return HuggingFaceTranscriber(
        client,
        token="hf_test",
        base_url="https://router.huggingface.co/hf-inference/models",
        model=model,
        provider_name=provider,
        language="en",
        timeout_seconds=1,
    )


async def test_transcription_chain_uses_secondary_model_after_primary_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if "NCAIR1" in str(request.url):
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"text": "There is a fire"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        chain = TranscriptionChain(
            [
                transcriber(client, "NCAIR1/NigerianAccentedEnglish", "n-atlas"),
                transcriber(client, "openai/whisper-large-v3", "whisper"),
            ]
        )
        result = await chain.transcribe(DownloadedAudio(b"audio", "audio/wav"))

    assert result.text == "There is a fire"
    assert result.provider == "whisper"
    assert result.fallback_used is True


@pytest.mark.parametrize(
    ("language", "expected_model"),
    [
        (LanguageCode.ENGLISH, "NCAIR1/NigerianAccentedEnglish"),
        (LanguageCode.YORUBA, "NCAIR1/Yoruba-ASR"),
        (LanguageCode.HAUSA, "NCAIR1/Hausa-ASR"),
        (LanguageCode.IGBO, "NCAIR1/Igbo-ASR"),
    ],
)
async def test_multilingual_transcriber_routes_to_selected_model(language, expected_model):
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json={"text": "Emergency report"}, request=request)

    models = {
        LanguageCode.ENGLISH: "NCAIR1/NigerianAccentedEnglish",
        LanguageCode.YORUBA: "NCAIR1/Yoruba-ASR",
        LanguageCode.HAUSA: "NCAIR1/Hausa-ASR",
        LanguageCode.IGBO: "NCAIR1/Igbo-ASR",
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = MultilingualTranscriber(
            client,
            token="hf_test",
            base_url="https://router.huggingface.co/hf-inference/models",
            natlas_models=models,
            fallback_model="openai/whisper-large-v3",
            timeout_seconds=1,
        )
        result = await router.transcribe(DownloadedAudio(b"audio", "audio/wav"), language)

    assert expected_model in requested_urls[0]
    assert result.model == expected_model
    assert result.language == language.value
    assert result.fallback_used is False
