from time import monotonic
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ...core.config import get_settings
from ...models import DownloadedAudio, LanguageCode, TranscriptionResponse
from ...services.audio import SUPPORTED_AUDIO_TYPES
from ...services.transcription import TranscriptionError
from ..dependencies import Transcriber

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])


@router.post("", response_model=TranscriptionResponse)
async def create_transcription(
    transcriber: Transcriber,
    language: Annotated[LanguageCode, Form()],
    audio: Annotated[UploadFile, File(description="A short emergency report as audio")],
) -> TranscriptionResponse:
    content_type = (audio.content_type or "").split(";", 1)[0].lower()
    if content_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload WAV or MP3 audio.",
        )

    max_bytes = get_settings().recording_max_bytes
    content = await audio.read(max_bytes + 1)
    await audio.close()
    if not content:
        raise HTTPException(status_code=422, detail="Audio file is empty.")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Audio file exceeds the upload limit.")

    started_at = monotonic()
    try:
        result = await transcriber.transcribe(
            DownloadedAudio(content=content, content_type=content_type),
            language,
        )
    except TranscriptionError as error:
        status_code = {
            "transcription_not_configured": status.HTTP_503_SERVICE_UNAVAILABLE,
            "transcription_timeout": status.HTTP_504_GATEWAY_TIMEOUT,
            "transcription_access_denied": status.HTTP_502_BAD_GATEWAY,
            "transcription_model_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
        }.get(error.code, status.HTTP_502_BAD_GATEWAY)
        raise HTTPException(status_code=status_code, detail=error.code) from error

    return TranscriptionResponse(
        text=result.text,
        language=language,
        provider=result.provider,
        model=result.model,
        fallback_used=result.fallback_used,
        elapsed_ms=round((monotonic() - started_at) * 1000),
    )
