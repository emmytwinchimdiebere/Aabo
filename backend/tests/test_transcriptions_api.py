from dataclasses import dataclass

import pytest

from app.api.dependencies import get_multilingual_transcriber
from app.models import LanguageCode, TranscriptResult
from app.services.transcription import TranscriptionError

pytestmark = pytest.mark.anyio


@dataclass
class FakeTranscriber:
    result: TranscriptResult | None = None
    error: TranscriptionError | None = None

    async def transcribe(self, audio, language: LanguageCode) -> TranscriptResult:
        assert audio.content == b"RIFFaudio"
        assert audio.content_type == "audio/wav"
        assert language is LanguageCode.IGBO
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


async def test_transcribes_uploaded_audio_with_selected_natlas_model(client):
    transcriber = FakeTranscriber(
        result=TranscriptResult(
            text="Oku di na ulo anyi",
            language="ig",
            provider="n-atlas",
            model="NCAIR1/Igbo-ASR",
        )
    )
    client._transport.app.dependency_overrides[get_multilingual_transcriber] = lambda: transcriber

    response = await client.post(
        "/transcriptions",
        data={"language": "ig"},
        files={"audio": ("report.wav", b"RIFFaudio", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() | {"elapsed_ms": 0} == {
        "text": "Oku di na ulo anyi",
        "language": "ig",
        "provider": "n-atlas",
        "model": "NCAIR1/Igbo-ASR",
        "fallback_used": False,
        "elapsed_ms": 0,
    }


async def test_rejects_unsupported_audio_type(client):
    response = await client.post(
        "/transcriptions",
        data={"language": "yo"},
        files={"audio": ("report.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 415


async def test_returns_service_unavailable_when_transcription_is_not_configured(client):
    transcriber = FakeTranscriber(error=TranscriptionError("transcription_not_configured"))
    client._transport.app.dependency_overrides[get_multilingual_transcriber] = lambda: transcriber

    response = await client.post(
        "/transcriptions",
        data={"language": "ig"},
        files={"audio": ("report.wav", b"RIFFaudio", "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "transcription_not_configured"
