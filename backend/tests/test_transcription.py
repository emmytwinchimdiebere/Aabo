import httpx
import pytest

from app.models import DownloadedAudio, LanguageCode
from app.services.transcription import (
    HuggingFaceTranscriber,
    MultilingualTranscriber,
    NatlasGatewayTranscriber,
    TranscriptionChain,
    has_repetition_loop,
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


async def test_natlas_gateway_sends_authenticated_multipart_audio():
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "text": "Oku di n'ahịa",
                "language": "ig",
                "model": "NCAIR1/Igbo-ASR",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transcriber = NatlasGatewayTranscriber(
            client,
            api_key="gateway-secret",
            base_url="https://natlas.example",
            language=LanguageCode.IGBO,
            model="NCAIR1/Igbo-ASR",
            timeout_seconds=1,
        )
        result = await transcriber.transcribe(DownloadedAudio(b"RIFFaudio", "audio/wav"))

    assert captured_request is not None
    assert captured_request.url == "https://natlas.example/v1/audio/transcriptions"
    assert captured_request.headers["authorization"] == "Bearer gateway-secret"
    assert b'name="language"' in captured_request.content
    assert b"ig" in captured_request.content
    assert b"RIFFaudio" in captured_request.content
    assert result.text == "Oku di n'ahịa"
    assert result.provider == "n-atlas"
    assert result.model == "NCAIR1/Igbo-ASR"


@pytest.mark.parametrize(
    "text",
    [
        "beacons have been burnt down " * 8,
        "Please help us now. The market is on fire. "
        "Please help us now. The market is on fire. "
        "Please help us now. The market is on fire.",
    ],
)
def test_detects_decoder_repetition_loops(text):
    assert has_repetition_loop(text) is True


def test_allows_legitimate_emergency_repetition():
    text = (
        "There is a fire at the market. Several buildings are affected. "
        "People are leaving the area and the fire is moving toward the nearby shops. "
        "Please send the fire service quickly."
    )
    assert has_repetition_loop(text) is False


async def test_natlas_repetition_loop_uses_whisper_fallback():
    repeated = "beacons have been burnt down " * 12

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "natlas.example":
            return httpx.Response(200, json={"text": repeated}, request=request)
        return httpx.Response(
            200,
            json={"text": "A fire broke out beside the market."},
            request=request,
        )

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
            natlas_gateway_url="https://natlas.example",
            natlas_api_key="secret",
        )
        result = await router.transcribe(
            DownloadedAudio(b"audio", "audio/wav"), LanguageCode.ENGLISH
        )

    assert result.text == "A fire broke out beside the market."
    assert result.provider == "whisper"
    assert result.fallback_used is True
