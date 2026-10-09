import httpx
import pytest

from app.services.audio import AudioDownloader, AudioDownloadError

pytestmark = pytest.mark.anyio


async def test_audio_downloader_accepts_supported_audio():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "audio/wav", "Content-Length": "4"},
            content=b"RIFF",
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        downloader = AudioDownloader(
            client,
            allowed_hosts=("recordings.example.com",),
            max_bytes=1024,
            timeout_seconds=1,
        )
        audio = await downloader.download("https://recordings.example.com/call.wav")

    assert audio.content == b"RIFF"
    assert audio.content_type == "audio/wav"


async def test_audio_downloader_rejects_unapproved_host():
    async with httpx.AsyncClient() as client:
        downloader = AudioDownloader(
            client,
            allowed_hosts=("recordings.example.com",),
            max_bytes=1024,
            timeout_seconds=1,
        )

        with pytest.raises(AudioDownloadError, match="recording_host_not_allowed"):
            await downloader.download("https://other.example.com/call.wav")


async def test_audio_downloader_enforces_size_limit():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"Content-Type": "audio/mpeg", "Content-Length": "2048"},
            content=b"audio",
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        downloader = AudioDownloader(
            client,
            allowed_hosts=("recordings.example.com",),
            max_bytes=1024,
            timeout_seconds=1,
        )

        with pytest.raises(AudioDownloadError, match="audio_too_large"):
            await downloader.download("https://recordings.example.com/call.mp3")
