from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import health, voice
from .core.config import get_settings
from .core.logging import configure_logging
from .database import get_database


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
        title="Aabo 112 API",
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
    application.include_router(voice.router)
    return application


app = create_app()
