import sqlite3
import xml.etree.ElementTree as ET

import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.anyio


async def start_call(client, session_id: str = "session-001"):
    return await client.post(
        "/voice/incoming",
        data={
            "callerNumber": "+2348000000000",
            "sessionId": session_id,
            "isActive": "1",
        },
    )


async def test_incoming_call_stores_hashed_identity_and_returns_provider_xml(client):
    response = await start_call(client)

    assert response.status_code == 200
    document = ET.fromstring(response.text)
    record = document.find("Record")
    assert record is not None
    assert record.attrib["callbackUrl"].endswith("/voice/recording?session_id=session-001")

    connection = sqlite3.connect(get_settings().database_path)
    stored_hash = connection.execute(
        "SELECT phone_hash FROM sessions WHERE id = ?", ("session-001",)
    ).fetchone()[0]
    connection.close()

    assert stored_hash != "+2348000000000"
    assert len(stored_hash) == 64


async def test_recording_callback_updates_session_state(client):
    await start_call(client)

    response = await client.post(
        "/voice/recording?session_id=session-001",
        data={
            "recordingUrl": "https://voice-provider.invalid/recording.wav",
            "durationInSeconds": "12",
        },
    )

    assert response.status_code == 202
    assert response.json()["duration_seconds"] == 12


async def test_unknown_recording_session_returns_not_found(client):
    response = await client.post(
        "/voice/recording?session_id=missing",
        data={
            "recordingUrl": "https://voice-provider.invalid/recording.wav",
            "durationInSeconds": "12",
        },
    )

    assert response.status_code == 404


async def test_call_end_closes_an_existing_session(client):
    await start_call(client)

    response = await client.post("/voice/end", data={"sessionId": "session-001"})

    assert response.status_code == 200
    assert response.json() == {"status": "ended", "session_id": "session-001"}
