import logging
from pathlib import Path
from uuid import uuid4

from ..repositories.incidents import IncidentRepository
from ..repositories.sessions import SessionRepository
from ..repositories.transcripts import TranscriptRepository
from .audio import AudioDownloader, AudioDownloadError
from .transcription import MultilingualTranscriber, TranscriptionError

logger = logging.getLogger(__name__)


class RecordingPipeline:
    def __init__(
        self,
        *,
        audio_downloader: AudioDownloader,
        transcriber: MultilingualTranscriber,
        sessions: SessionRepository,
        transcripts: TranscriptRepository,
        incidents: IncidentRepository,
        recording_storage_path: Path,
    ) -> None:
        self.audio_downloader = audio_downloader
        self.transcriber = transcriber
        self.sessions = sessions
        self.transcripts = transcripts
        self.incidents = incidents
        self.recording_storage_path = recording_storage_path

    def prepare(self, session_id: str) -> None:
        self.transcripts.mark_processing(session_id)

    async def process(
        self,
        session_id: str,
        recording_url: str,
        request_headers: dict[str, str] | None = None,
    ) -> None:
        try:
            audio = await self.audio_downloader.download(
                recording_url,
                request_headers=request_headers,
            )
            recording_path = self._store_recording(audio.content, audio.content_type)
            self.incidents.attach_recording(session_id, recording_path, audio.content_type)
            language = self.sessions.get_language(session_id)
            result = await self.transcriber.transcribe(audio, language)
            self.transcripts.save(session_id, result)
            logger.info(
                "Transcription complete",
                extra={"session_id": session_id, "provider": result.provider},
            )
        except AudioDownloadError as error:
            self.transcripts.mark_manual_required(session_id, error.code)
            logger.error(
                "Recording download failed",
                extra={"session_id": session_id, "code": error.code},
            )
        except TranscriptionError as error:
            self.transcripts.mark_manual_required(session_id, error.code)
            logger.error(
                "Transcription failed",
                extra={"session_id": session_id, "code": error.code},
            )

    def _store_recording(self, content: bytes, content_type: str) -> Path:
        extension = ".mp3" if content_type in {"audio/mpeg", "audio/mp3"} else ".wav"
        storage_root = self.recording_storage_path.resolve()
        storage_root.mkdir(parents=True, exist_ok=True)
        path = (storage_root / f"{uuid4().hex}{extension}").resolve()
        if storage_root not in path.parents:
            raise AudioDownloadError("invalid_recording_path")
        path.write_bytes(content)
        return path
