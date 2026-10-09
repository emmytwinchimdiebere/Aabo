from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_recording_pipeline, get_voicebip_sms_service
from app.core.config import get_settings
from app.database import get_database
from app.main import create_app
from app.services.sms import SmsAcknowledgement


class FakeRecordingPipeline:
    def __init__(self) -> None:
        self.prepared: list[str] = []
        self.processed: list[tuple[str, str, dict[str, str] | None]] = []

    def prepare(self, session_id: str) -> None:
        self.prepared.append(session_id)

    async def process(
        self,
        session_id: str,
        recording_url: str,
        request_headers: dict[str, str] | None = None,
    ) -> None:
        self.processed.append((session_id, recording_url, request_headers))


class FakeSmsService:
    def __init__(self) -> None:
        self.reports: list[dict[str, str]] = []
        self.acknowledgements: list[SmsAcknowledgement] = []
        self.delivery_receipts: list[tuple[str, str]] = []

    def register_report(self, **report: str) -> SmsAcknowledgement:
        self.reports.append(report)
        acknowledgement = SmsAcknowledgement(
            report_id=report["message_id"],
            agent_id=report["agent_id"],
            from_number=report["recipient_number"],
            to_number=report["sender_number"],
        )
        return acknowledgement

    async def send_acknowledgement(self, acknowledgement: SmsAcknowledgement) -> None:
        self.acknowledgements.append(acknowledgement)

    def update_delivery_status(self, message_id: str, status: str) -> None:
        self.delivery_receipts.append((message_id, status))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def recording_pipeline() -> FakeRecordingPipeline:
    return FakeRecordingPipeline()


@pytest.fixture
def sms_service() -> FakeSmsService:
    return FakeSmsService()


@pytest.fixture
async def client(
    tmp_path, monkeypatch, recording_pipeline, sms_service
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("PHONE_HASH_SALT", "test-salt")
    monkeypatch.setenv("VOICEBIP_API_KEY", "pk_live_test")
    monkeypatch.setenv("VOICEBIP_SIGNING_SECRET", "voicebip-test-secret")
    monkeypatch.setenv("VOICEBIP_ENGLISH_AGENT_ID", "agt-en")
    monkeypatch.setenv("VOICEBIP_YORUBA_AGENT_ID", "agt-yo")
    monkeypatch.setenv("VOICEBIP_HAUSA_AGENT_ID", "agt-ha")
    monkeypatch.setenv("VOICEBIP_IGBO_AGENT_ID", "agt-ig")
    monkeypatch.setenv("RECORDING_ALLOWED_HOSTS", "api.voicebip.com")
    monkeypatch.setenv("RECORDING_STORAGE_PATH", str(tmp_path / "recordings"))
    get_settings.cache_clear()
    get_database.cache_clear()

    application = create_app()
    application.dependency_overrides[get_recording_pipeline] = lambda: recording_pipeline
    application.dependency_overrides[get_voicebip_sms_service] = lambda: sms_service
    transport = ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    get_database.cache_clear()
    get_settings.cache_clear()
