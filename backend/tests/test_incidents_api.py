import sqlite3

import pytest

from app.core.config import get_settings
from app.database import get_database
from app.repositories.incidents import IncidentRepository

pytestmark = pytest.mark.anyio


async def test_web_incident_preserves_audio_and_both_transcripts(client):
    response = await client.post(
        "/incidents/web",
        data={
            "language": "ig",
            "emergency_type": "Medical",
            "confirmed_address": "No. 19, Osumeyi Street, Awada",
            "raw_transcript": "number 19 osimu enye street in awaga",
            "confirmed_transcript": "Biko bia No. 19, Osumeyi Street, Awada",
            "duration_seconds": "13",
            "latitude": "6.117",
            "longitude": "6.783",
            "training_consent": "true",
        },
        files={"audio": ("report.wav", b"RIFFaudio", "audio/wav")},
    )

    assert response.status_code == 201
    incident_id = response.json()["incident_id"]

    incidents = await client.get("/incidents")
    assert incidents.status_code == 200
    assert incidents.json() == [
        {
            "incident_id": incident_id,
            "created_at": incidents.json()[0]["created_at"],
            "language": "ig",
            "emergency_type": "Medical",
            "confirmed_address": "No. 19, Osumeyi Street, Awada",
            "raw_transcript": "number 19 osimu enye street in awaga",
            "confirmed_transcript": "Biko bia No. 19, Osumeyi Street, Awada",
            "latitude": 6.117,
            "longitude": 6.783,
            "duration_seconds": 13,
            "dispatcher_status": "pending",
            "has_recording": True,
        }
    ]

    recording = await client.get(f"/incidents/{incident_id}/recording")
    assert recording.status_code == 200
    assert recording.headers["content-type"] == "audio/wav"
    assert recording.content == b"RIFFaudio"

    with sqlite3.connect(get_settings().database_path) as connection:
        feedback = connection.execute(
            """
            SELECT training_consent, training_review_status
            FROM incidents WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()
    assert feedback == (1, "pending")

    repository = IncidentRepository(get_database())
    pending = repository.list_transcription_feedback("pending")
    assert [record["id"] for record in pending] == [incident_id]
    assert repository.set_training_review_status(incident_id, "approved") is True
    approved = repository.list_transcription_feedback("approved")
    assert [record["id"] for record in approved] == [incident_id]


async def test_web_incident_requires_confirmed_address(client):
    response = await client.post(
        "/incidents/web",
        data={
            "language": "en",
            "emergency_type": "Fire",
            "confirmed_address": " ",
            "raw_transcript": "There is a fire",
            "confirmed_transcript": "There is a fire",
            "duration_seconds": "4",
        },
        files={"audio": ("report.wav", b"RIFFaudio", "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Confirmed address is required."
