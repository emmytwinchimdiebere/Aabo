import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Query
from fastapi.responses import Response

from ...models import RecordingAcceptedResponse, SessionClosedResponse
from ...repositories.sessions import SessionNotFoundError
from ..dependencies import Pipeline, VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)


@router.post("/incoming", response_class=Response)
def incoming_call(
    service: VoiceService,
    caller_number: Annotated[str, Form(alias="callerNumber")],
    session_id: Annotated[str, Form(alias="sessionId")],
    is_active: Annotated[str, Form(alias="isActive")],
) -> Response:
    del is_active
    xml = service.begin_call(session_id=session_id, caller_number=caller_number)
    return Response(content=xml, media_type="application/xml")


@router.post(
    "/recording",
    response_model=RecordingAcceptedResponse,
)
def recording_ready(
    service: VoiceService,
    pipeline: Pipeline,
    background_tasks: BackgroundTasks,
    session_id: Annotated[str, Query(min_length=1)],
    recording_url: Annotated[str, Form(alias="recordingUrl")],
    duration_seconds: Annotated[int, Form(alias="durationInSeconds", ge=0)],
) -> RecordingAcceptedResponse:
    try:
        service.accept_recording(session_id, duration_seconds)
        pipeline.prepare(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Call session not found") from error

    background_tasks.add_task(pipeline.process, session_id, recording_url)
    logger.info("Recording received", extra={"session_id": session_id})
    return RecordingAcceptedResponse(
        session_id=session_id,
        duration_seconds=duration_seconds,
    )


@router.post("/end", response_model=SessionClosedResponse)
def call_ended(
    service: VoiceService,
    session_id: Annotated[str, Form(alias="sessionId")],
) -> SessionClosedResponse:
    try:
        service.end_call(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Call session not found") from error
    return SessionClosedResponse(session_id=session_id)
