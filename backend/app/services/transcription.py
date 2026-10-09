import logging
from collections.abc import Sequence
from urllib.parse import quote

import httpx

from ..models import DownloadedAudio, TranscriptResult

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class HuggingFaceTranscriber:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        token: str | None,
        base_url: str,
        model: str,
        provider_name: str,
        language: str | None,
        timeout_seconds: float,
    ) -> None:
        self.client = client
        self.token = token
        self.base_url = base_url
        self.model = model
        self.provider_name = provider_name
        self.language = language
        self.timeout_seconds = timeout_seconds

    async def transcribe(self, audio: DownloadedAudio) -> TranscriptResult:
        if not self.token:
            raise TranscriptionError("transcription_not_configured")

        model_path = quote(self.model, safe="/")
        try:
            response = await self.client.post(
                f"{self.base_url}/{model_path}",
                content=audio.content,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": audio.content_type,
                },
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise TranscriptionError("transcription_timeout") from error
        except httpx.HTTPError as error:
            raise TranscriptionError("transcription_request_failed") from error

        if response.status_code == 503:
            raise TranscriptionError("transcription_model_unavailable")
        if response.status_code in {401, 403}:
            raise TranscriptionError("transcription_access_denied")
        if response.status_code != 200:
            raise TranscriptionError("transcription_request_failed")

        try:
            payload = response.json()
            text = payload["text"].strip()
        except (KeyError, TypeError, ValueError) as error:
            raise TranscriptionError("invalid_transcription_response") from error
        if not text:
            raise TranscriptionError("empty_transcript")

        return TranscriptResult(
            text=text,
            language=self.language,
            confidence=None,
            provider=self.provider_name,
            model=self.model,
        )


class TranscriptionChain:
    def __init__(self, transcribers: Sequence[HuggingFaceTranscriber]) -> None:
        if not transcribers:
            raise ValueError("At least one transcriber is required")
        self.transcribers = transcribers

    async def transcribe(self, audio: DownloadedAudio) -> TranscriptResult:
        final_error = "transcription_failed"
        for index, transcriber in enumerate(self.transcribers):
            try:
                result = await transcriber.transcribe(audio)
                if index == 0:
                    return result
                return TranscriptResult(
                    text=result.text,
                    language=result.language,
                    confidence=result.confidence,
                    provider=result.provider,
                    model=result.model,
                    fallback_used=True,
                )
            except TranscriptionError as error:
                final_error = error.code
                logger.warning(
                    "Transcription provider failed",
                    extra={"provider": transcriber.provider_name, "code": error.code},
                )

        raise TranscriptionError(final_error)
