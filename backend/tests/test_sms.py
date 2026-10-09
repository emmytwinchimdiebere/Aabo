import json
import sqlite3

import httpx
import pytest

from app.core.config import get_settings
from app.database import Database
from app.repositories.text_reports import TextReportRepository
from app.services.sms import VoicebipSmsService

pytestmark = pytest.mark.anyio


async def test_sms_report_is_hashed_persisted_and_acknowledged(tmp_path, monkeypatch):
    database_path = tmp_path / "sms.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("PHONE_HASH_SALT", "sms-test-salt")
    monkeypatch.setenv("VOICEBIP_API_KEY", "pk_live_test")
    get_settings.cache_clear()
    settings = get_settings()
    database = Database(database_path)
    database.migrate()

    async def send_message(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer pk_live_test"
        assert payload == {
            "agent_id": "agt-test",
            "channel": "sms",
            "from_number": "+2342013502017",
            "to_number": "+2348000000000",
            "body": settings.sms_acknowledgement_text,
        }
        return httpx.Response(201, json={"message_id": "msg-ack", "status": "queued"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(send_message)) as http_client:
        service = VoicebipSmsService(
            http_client=http_client,
            reports=TextReportRepository(database),
            settings=settings,
        )
        acknowledgement = service.register_report(
            message_id="msg-report",
            agent_id="agt-test",
            sender_number="+2348000000000",
            recipient_number="+2342013502017",
            body="  There is flooding near the bridge.  ",
        )
        assert acknowledgement is not None
        await service.send_acknowledgement(acknowledgement)
        service.update_delivery_status("msg-ack", "DELIVRD")

        duplicate = service.register_report(
            message_id="msg-report",
            agent_id="agt-test",
            sender_number="+2348000000000",
            recipient_number="+2342013502017",
            body="There is flooding near the bridge.",
        )
        assert duplicate is None

    connection = sqlite3.connect(database_path)
    row = connection.execute(
        """
        SELECT sender_hash, body, status, acknowledgement_message_id,
               acknowledgement_status
        FROM text_reports WHERE id = ?
        """,
        ("msg-report",),
    ).fetchone()
    connection.close()

    assert row is not None
    assert row[0] != "+2348000000000"
    assert len(row[0]) == 64
    assert row[1:] == (
        "There is flooding near the bridge.",
        "acknowledged",
        "msg-ack",
        "DELIVRD",
    )
    get_settings.cache_clear()
