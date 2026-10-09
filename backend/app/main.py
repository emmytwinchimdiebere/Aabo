from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import health, incidents, locations, transcriptions, voice, voicebip
from .core.config import PROJECT_ROOT, get_settings
from .core.logging import configure_logging
from .database import get_database

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    settings.validate()
    get_database().migrate()
    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        application.state.http_client = http_client
        yield


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    application = FastAPI(
        title="Aabo API",
        description="Voice emergency intake and incident coordination API.",
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health.router)
    application.include_router(incidents.router)
    application.include_router(locations.router)
    application.include_router(transcriptions.router)
    application.include_router(voice.router)
    application.include_router(voicebip.router)
    if FRONTEND_DIST.is_dir():
        @application.get("/dispatch", include_in_schema=False)
        def dispatcher_console() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

        application.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="console")
    return application


app = create_app()
