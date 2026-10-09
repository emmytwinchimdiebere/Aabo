from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_recording_pipeline
from app.core.config import get_settings
from app.database import get_database
from app.main import create_app


class FakeRecordingPipeline:
    def __init__(self) -> None:
        self.prepared: list[str] = []
        self.processed: list[tuple[str, str]] = []

    def prepare(self, session_id: str) -> None:
        self.prepared.append(session_id)

    async def process(self, session_id: str, recording_url: str) -> None:
        self.processed.append((session_id, recording_url))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def recording_pipeline() -> FakeRecordingPipeline:
    return FakeRecordingPipeline()


@pytest.fixture
async def client(tmp_path, monkeypatch, recording_pipeline) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("PHONE_HASH_SALT", "test-salt")
    get_settings.cache_clear()
    get_database.cache_clear()

    application = create_app()
    application.dependency_overrides[get_recording_pipeline] = lambda: recording_pipeline
    transport = ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    get_database.cache_clear()
    get_settings.cache_clear()
