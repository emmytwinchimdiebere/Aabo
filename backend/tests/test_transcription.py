import httpx
import pytest

from app.models import DownloadedAudio
from app.services.transcription import HuggingFaceTranscriber, TranscriptionChain

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
