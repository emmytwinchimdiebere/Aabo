from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.database import get_database
from app.main import create_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(tmp_path, monkeypatch) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("PHONE_HASH_SALT", "test-salt")
    get_settings.cache_clear()
    get_database.cache_clear()

    application = create_app()
    transport = ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    get_database.cache_clear()
    get_settings.cache_clear()
