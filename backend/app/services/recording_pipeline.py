import logging

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
    ) -> None:
        self.audio_downloader = audio_downloader
        self.transcriber = transcriber
        self.sessions = sessions
        self.transcripts = transcripts

    def prepare(self, session_id: str) -> None:
        self.transcripts.mark_processing(session_id)

    async def process(self, session_id: str, recording_url: str) -> None:
        try:
            audio = await self.audio_downloader.download(recording_url)
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
