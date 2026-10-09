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


async def test_audio_downloader_sends_credentials_only_to_original_host():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "api.voicebip.com":
            return httpx.Response(
                302,
                headers={"Location": "https://media.voicebip.com/call.wav"},
                request=request,
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "audio/wav"},
            content=b"RIFF",
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        downloader = AudioDownloader(
            client,
            allowed_hosts=("api.voicebip.com", "media.voicebip.com"),
            max_bytes=1024,
            timeout_seconds=1,
        )
        await downloader.download(
            "https://api.voicebip.com/v1/calls/call-1/recording",
            request_headers={"Authorization": "Bearer private"},
        )

    assert requests[0].headers["Authorization"] == "Bearer private"
    assert "Authorization" not in requests[1].headers
