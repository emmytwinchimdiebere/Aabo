import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Protocol
from urllib.parse import quote

import httpx

from ..models import DownloadedAudio, LanguageCode, TranscriptResult

logger = logging.getLogger(__name__)

_WORD_PATTERN = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


def has_repetition_loop(text: str) -> bool:
    """Detect decoder loops without rejecting normal repeated emergency words."""

    words = [word.casefold() for word in _WORD_PATTERN.findall(text)]
    if len(words) < 18:
        return False

    for phrase_size in range(3, min(12, len(words) // 3) + 1):
        for start in range(0, len(words) - phrase_size * 3 + 1):
            phrase = words[start : start + phrase_size]
            if (
                words[start + phrase_size : start + phrase_size * 2] == phrase
                and words[start + phrase_size * 2 : start + phrase_size * 3] == phrase
            ):
                return True

    four_grams = [tuple(words[index : index + 4]) for index in range(len(words) - 3)]
    return bool(four_grams and Counter(four_grams).most_common(1)[0][1] >= 5)


class TranscriptionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AudioTranscriber(Protocol):
    provider_name: str

    async def transcribe(self, audio: DownloadedAudio) -> TranscriptResult: ...


class NatlasGatewayTranscriber:
    provider_name = "n-atlas"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        base_url: str,
        language: LanguageCode,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def transcribe(self, audio: DownloadedAudio) -> TranscriptResult:
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                data={"language": self.language.value, "response_format": "verbose_json"},
                files={"file": ("emergency-report.wav", audio.content, audio.content_type)},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise TranscriptionError("transcription_timeout") from error
        except httpx.HTTPError as error:
            raise TranscriptionError("transcription_request_failed") from error

        if response.status_code in {401, 403}:
            raise TranscriptionError("transcription_access_denied")
        if response.status_code in {502, 503}:
            raise TranscriptionError("transcription_model_unavailable")
        if response.status_code == 504:
            raise TranscriptionError("transcription_timeout")
        if response.status_code != 200:
            raise TranscriptionError("transcription_request_failed")

        try:
            payload = response.json()
            text = payload["text"].strip()
        except (KeyError, TypeError, ValueError) as error:
            raise TranscriptionError("invalid_transcription_response") from error
        if not text:
            raise TranscriptionError("empty_transcript")
        if has_repetition_loop(text):
            raise TranscriptionError("degenerate_transcript")

        return TranscriptResult(
            text=text,
            language=self.language.value,
            confidence=None,
            provider=self.provider_name,
            model=payload.get("model", self.model),
        )


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
        if has_repetition_loop(text):
            raise TranscriptionError("degenerate_transcript")

        return TranscriptResult(
            text=text,
            language=self.language,
            confidence=None,
            provider=self.provider_name,
            model=self.model,
        )


class TranscriptionChain:
    def __init__(self, transcribers: Sequence[AudioTranscriber]) -> None:
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


class MultilingualTranscriber:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        token: str | None,
        base_url: str,
        natlas_models: Mapping[LanguageCode, str],
        fallback_model: str,
        timeout_seconds: float,
        natlas_gateway_url: str | None = None,
        natlas_api_key: str | None = None,
    ) -> None:
        if set(natlas_models) != set(LanguageCode):
            raise ValueError("A N-ATLaS model must be configured for every language")
        self.client = client
        self.token = token
        self.base_url = base_url
        self.natlas_models = natlas_models
        self.fallback_model = fallback_model
        self.timeout_seconds = timeout_seconds
        self.natlas_gateway_url = natlas_gateway_url
        self.natlas_api_key = natlas_api_key

    async def transcribe(self, audio: DownloadedAudio, language: LanguageCode) -> TranscriptResult:
        if self.natlas_gateway_url and self.natlas_api_key:
            primary: AudioTranscriber = NatlasGatewayTranscriber(
                self.client,
                api_key=self.natlas_api_key,
                base_url=self.natlas_gateway_url,
                language=language,
                model=self.natlas_models[language],
                timeout_seconds=self.timeout_seconds,
            )
        else:
            primary = HuggingFaceTranscriber(
                    self.client,
                    token=self.token,
                    base_url=self.base_url,
                    model=self.natlas_models[language],
                    provider_name="n-atlas",
                    language=language.value,
                    timeout_seconds=self.timeout_seconds,
                )
        chain = TranscriptionChain(
            [
                primary,
                HuggingFaceTranscriber(
                    self.client,
                    token=self.token,
                    base_url=self.base_url,
                    model=self.fallback_model,
                    provider_name="whisper",
                    language=language.value,
                    timeout_seconds=self.timeout_seconds,
                ),
            ]
        )
        return await chain.transcribe(audio)
