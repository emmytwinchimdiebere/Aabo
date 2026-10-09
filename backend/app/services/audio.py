import ipaddress
from urllib.parse import urljoin, urlsplit

import httpx

from ..models import DownloadedAudio

SUPPORTED_AUDIO_TYPES = {
    "application/octet-stream",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
}


class AudioDownloadError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AudioDownloader:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        allowed_hosts: tuple[str, ...],
        max_bytes: int,
        timeout_seconds: float,
        max_redirects: int = 3,
    ) -> None:
        self.client = client
        self.allowed_hosts = {host.lower() for host in allowed_hosts}
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds
        self.max_redirects = max_redirects

    async def download(
        self,
        url: str,
        *,
        request_headers: dict[str, str] | None = None,
    ) -> DownloadedAudio:
        current_url = url
        credential_host = (urlsplit(url).hostname or "").lower()

        for redirect_count in range(self.max_redirects + 1):
            self._validate_url(current_url)
            try:
                current_host = (urlsplit(current_url).hostname or "").lower()
                headers = {"Accept": "audio/*, application/octet-stream"}
                if request_headers and current_host == credential_host:
                    headers.update(request_headers)
                async with self.client.stream(
                    "GET",
                    current_url,
                    timeout=self.timeout_seconds,
                    headers=headers,
                ) as response:
                    if response.is_redirect:
                        if redirect_count == self.max_redirects:
                            raise AudioDownloadError("too_many_redirects")
                        location = response.headers.get("location")
                        if not location:
                            raise AudioDownloadError("invalid_redirect")
                        current_url = urljoin(str(response.url), location)
                        continue

                    if response.status_code != 200:
                        raise AudioDownloadError("provider_download_failed")

                    content_type = response.headers.get("content-type", "")
                    content_type = content_type.split(";", 1)[0].strip().lower()
                    if content_type not in SUPPORTED_AUDIO_TYPES:
                        raise AudioDownloadError("unsupported_audio_type")

                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > self.max_bytes:
                        raise AudioDownloadError("audio_too_large")

                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > self.max_bytes:
                            raise AudioDownloadError("audio_too_large")

                    if not content:
                        raise AudioDownloadError("empty_audio")
                    return DownloadedAudio(bytes(content), content_type)
            except AudioDownloadError:
                raise
            except httpx.TimeoutException as error:
                raise AudioDownloadError("provider_timeout") from error
            except httpx.HTTPError as error:
                raise AudioDownloadError("provider_download_failed") from error

        raise AudioDownloadError("too_many_redirects")

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()

        if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
            raise AudioDownloadError("invalid_recording_url")
        if hostname == "localhost" or hostname.endswith(".local"):
            raise AudioDownloadError("recording_host_not_allowed")
        if self.allowed_hosts and hostname not in self.allowed_hosts:
            raise AudioDownloadError("recording_host_not_allowed")

        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return
        if not address.is_global:
            raise AudioDownloadError("recording_host_not_allowed")
