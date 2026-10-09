import hashlib
import hmac
import json
import sqlite3
import time

import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.anyio


def signed_request(payload: dict, *, event_id: str | None = None):
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    message = timestamp.encode("ascii") + b"." + raw_body
    digest = hmac.new(b"voicebip-test-secret", message, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Voicebip-Timestamp": timestamp,
        "X-Voicebip-Signature": f"sha256={digest}",
    }
    if event_id:
        headers["X-Voicebip-Event-ID"] = event_id
    return raw_body, headers


async def post_signed(client, payload: dict, *, event_id: str | None = None):
    content, headers = signed_request(payload, event_id=event_id)
    return await client.post("/webhooks/voicebip", content=content, headers=headers)


async def test_call_initiated_creates_a_hashed_session(client):
    response = await post_signed(
        client,
        {
            "event_id": "evt-start",
            "event_type": "call.initiated",
            "channel": "voice",
            "from": "+2348000000000",
            "payload": {
                "call_id": "call-001",
                "direction": "inbound",
                "from_number": "+2348000000000",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"received": True}
    connection = sqlite3.connect(get_settings().database_path)
    phone_hash = connection.execute(
        "SELECT phone_hash FROM sessions WHERE id = ?", ("call-001",)
    ).fetchone()[0]
    connection.close()
    assert phone_hash != "+2348000000000"
    assert len(phone_hash) == 64


async def test_first_byom_turn_selects_language_and_requests_report(client):
    response = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": "call-hausa",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "Hausa",
            "messages": [{"role": "caller", "text": "Hausa"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["end_call"] is False
    assert "gaggawa" in response.json()["text"]
    connection = sqlite3.connect(get_settings().database_path)
    language = connection.execute(
        "SELECT language FROM sessions WHERE id = ?", ("call-hausa",)
    ).fetchone()[0]
    connection.close()
    assert language == "ha"


async def test_direct_english_report_detects_language_and_requests_location(client):
    response = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": "call-report",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "There is a fire near the market",
            "messages": [
                {"role": "caller", "text": "English"},
                {"role": "agent", "text": "Please describe your emergency."},
                {"role": "caller", "text": "There is a fire near the market"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["end_call"] is False
    assert "where you are" in response.json()["text"]


@pytest.mark.parametrize(
    ("call_id", "report", "expected_language", "prompt_fragment"),
    [
        ("call-auto-en", "There is a fire and someone is hurt", "en", "where you are"),
        ("call-auto-yo", "Jowo, ina n jo ni oja", "yo", "ibi ti o wa"),
        ("call-auto-ha", "Don Allah, akwai wuta a kasuwa", "ha", "inda kake"),
        ("call-auto-ig", "Biko, oku di n'ahia ugbu a", "ig", "ebe ino"),
    ],
)
async def test_direct_report_detects_supported_language(
    client, call_id, report, expected_language, prompt_fragment
):
    response = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": call_id,
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": report,
            "messages": [{"role": "caller", "text": report}],
        },
    )

    assert response.status_code == 200
    assert response.json()["end_call"] is False
    assert prompt_fragment in response.json()["text"]
    connection = sqlite3.connect(get_settings().database_path)
    language = connection.execute(
        "SELECT language FROM sessions WHERE id = ?", (call_id,)
    ).fetchone()[0]
    connection.close()
    assert language == expected_language


async def test_low_confidence_input_asks_for_language(client):
    first = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": "call-clarify",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "Okay",
            "messages": [{"role": "caller", "text": "Okay"}],
        },
    )
    second = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": "call-clarify",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "Yoruba",
            "messages": [{"role": "caller", "text": "Yoruba"}],
        },
    )

    assert "Say one for English" in first.json()["text"]
    assert "ibi ti o wa" in second.json()["text"]
    connection = sqlite3.connect(get_settings().database_path)
    emergency_text = connection.execute(
        "SELECT emergency_text FROM agent_conversations WHERE session_id = ?",
        ("call-clarify",),
    ).fetchone()[0]
    connection.close()
    assert emergency_text is None


async def test_recognizable_english_word_does_not_loop_on_language(client):
    response = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": "call-please-regression",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "Please.",
            "messages": [{"role": "caller", "text": "Please."}],
        },
    )

    assert response.status_code == 200
    assert "where you are" in response.json()["text"]


async def test_repeated_spoken_number_selects_igbo(client):
    response = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-test",
            "call_id": "call-repeated-four",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "Four four four.",
            "messages": [{"role": "caller", "text": "Four four four."}],
        },
    )

    assert response.status_code == 200
    assert "ebe ino" in response.json()["text"]
    connection = sqlite3.connect(get_settings().database_path)
    language = connection.execute(
        "SELECT language FROM sessions WHERE id = ?", ("call-repeated-four",)
    ).fetchone()[0]
    connection.close()
    assert language == "ig"


async def test_language_specific_agent_overrides_bad_auto_transcription(client):
    response = await post_signed(
        client,
        {
            "event": "turn",
            "agent_id": "agt-ig",
            "call_id": "call-igbo-route",
            "from_number": "+2348000000000",
            "to_number": "+2342013502017",
            "transcription": "You both you both.",
            "messages": [{"role": "caller", "text": "You both you both."}],
        },
    )

    assert response.status_code == 200
    assert "ebe ino" in response.json()["text"]
    connection = sqlite3.connect(get_settings().database_path)
    language = connection.execute(
        "SELECT language FROM sessions WHERE id = ?", ("call-igbo-route",)
    ).fetchone()[0]
    connection.close()
    assert language == "ig"


async def test_language_clarification_falls_back_to_english_after_one_retry(client):
    call_id = "call-language-fallback"
    base = {
        "event": "turn",
        "agent_id": "agt-test",
        "call_id": call_id,
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
    }
    first = await post_signed(
        client,
        {
            **base,
            "transcription": "Okay",
            "messages": [{"role": "caller", "text": "Okay"}],
        },
    )
    second = await post_signed(
        client,
        {
            **base,
            "transcription": "Maybe",
            "messages": [
                {"role": "caller", "text": "Okay"},
                {"role": "agent", "text": first.json()["text"]},
                {"role": "caller", "text": "Maybe"},
            ],
        },
    )

    assert "Say one for English" in first.json()["text"]
    assert "where you are" in second.json()["text"]


async def test_location_is_confirmed_before_incident_tool_runs(client):
    base = {
        "event": "turn",
        "agent_id": "agt-test",
        "call_id": "call-location-flow",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }

    for utterance in (
        "English",
        "Balogun Market, Lagos Island",
        "yes",
        "There is a fire in a shop",
    ):
        response = await post_signed(client, {**base, "transcription": utterance})

    assert response.status_code == 200
    assert response.json()["end_call"] is False
    assert "There is a fire in a shop" in response.json()["text"]
    connection = sqlite3.connect(get_settings().database_path)
    connection.row_factory = sqlite3.Row
    before_confirmation = connection.execute(
        "SELECT id FROM incidents WHERE session_id = ?",
        ("call-location-flow",),
    ).fetchone()
    connection.close()
    assert before_confirmation is None

    response = await post_signed(client, {**base, "transcription": "yes"})
    assert response.json()["end_call"] is True
    assert response.json()["text"] == (
        "Your report is with the dispatcher. Stay calm and move to safety if you can."
    )
    connection = sqlite3.connect(get_settings().database_path)
    connection.row_factory = sqlite3.Row
    incident = connection.execute(
        """
        SELECT language, emergency_type, spoken_location, location_match, transcript
        FROM incidents WHERE session_id = ?
        """,
        ("call-location-flow",),
    ).fetchone()
    connection.close()
    assert dict(incident) == {
        "language": "en",
        "emergency_type": "fire",
        "spoken_location": "Balogun Market, Lagos Island",
        "location_match": "caller_confirmed:spoken_landmark",
        "transcript": "There is a fire in a shop",
    }


async def test_emergency_correction_replaces_text_before_tool_runs(client):
    base = {
        "event": "turn",
        "agent_id": "agt-test",
        "call_id": "call-emergency-correction",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }
    for utterance in (
        "English",
        "Balogun Market, Lagos Island",
        "yes",
        "Someone fell down",
        "no",
        "Someone is unconscious and bleeding",
    ):
        response = await post_signed(client, {**base, "transcription": utterance})

    assert "Someone is unconscious and bleeding" in response.json()["text"]
    response = await post_signed(client, {**base, "transcription": "that is correct"})
    assert response.json()["end_call"] is True

    connection = sqlite3.connect(get_settings().database_path)
    incident = connection.execute(
        "SELECT emergency_type, transcript FROM incidents WHERE session_id = ?",
        ("call-emergency-correction",),
    ).fetchone()
    connection.close()
    assert incident == ("medical", "Someone is unconscious and bleeding")


@pytest.mark.parametrize("confirmation", ["bẹẹni ni", "na'am", "ọ dị mma"])
async def test_multilingual_positive_confirmations_are_understood(client, confirmation):
    base = {
        "event": "turn",
        "agent_id": "agt-en",
        "call_id": f"call-confirm-{confirmation}",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }
    for utterance in (
        "English",
        "Central Market, Enugu",
        "yes",
        "There is a fire",
    ):
        await post_signed(client, {**base, "transcription": utterance})

    response = await post_signed(client, {**base, "transcription": confirmation})
    assert response.json()["end_call"] is True


async def test_repeated_no_restarts_location_collection(client):
    base = {
        "event": "turn",
        "agent_id": "agt-test",
        "call_id": "call-repeated-no",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }
    await post_signed(client, {**base, "transcription": "English"})
    await post_signed(client, {**base, "transcription": "Balogun Market, Lagos"})
    response = await post_signed(client, {**base, "transcription": "No. No."})

    assert response.status_code == 200
    assert "tell me where you are" in response.json()["text"]
    assert "I heard" not in response.json()["text"]


async def test_spoken_location_correction_is_saved_and_confirmed(client):
    base = {
        "event": "turn",
        "agent_id": "agt-test",
        "call_id": "call-location-correction",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }
    await post_signed(client, {**base, "transcription": "English"})
    await post_signed(client, {**base, "transcription": "Balogun Market, Lagos"})

    response = await post_signed(
        client,
        {**base, "transcription": "No. 19 Osumeyi Street, Awada"},
    )

    assert response.status_code == 200
    assert "No. 19 Osumeyi Street, Awada" in response.json()["text"]
    assert "Is that correct" in response.json()["text"]
    response = await post_signed(client, {**base, "transcription": "yes"})
    assert response.status_code == 200
    assert "Location confirmed" in response.json()["text"]


async def test_broad_location_prompts_for_a_landmark(client):
    base = {
        "event": "turn",
        "agent_id": "agt-test",
        "call_id": "call-broad-location",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }
    await post_signed(client, {**base, "transcription": "English"})
    response = await post_signed(client, {**base, "transcription": "Lagos"})

    assert response.status_code == 200
    assert "more exact place" in response.json()["text"]
    assert response.json()["end_call"] is False


async def test_second_partial_location_is_confirmed_instead_of_looping(client):
    base = {
        "event": "turn",
        "agent_id": "agt-en",
        "call_id": "call-partial-location",
        "from_number": "+2348000000000",
        "to_number": "+2342013502017",
        "messages": [],
    }
    await post_signed(client, {**base, "transcription": "English"})

    first = await post_signed(client, {**base, "transcription": "Awada"})
    second = await post_signed(client, {**base, "transcription": "Osumeyi"})

    assert "more exact place" in first.json()["text"]
    assert "Awada, Osumeyi" in second.json()["text"]
    assert "Is that correct" in second.json()["text"]


async def test_completed_call_accepts_nested_recording_url(client, recording_pipeline):
    response = await post_signed(
        client,
        {
            "event_id": "evt-complete-nested-recording",
            "event_type": "call.completed",
            "channel": "voice",
            "from": "+2348000000000",
            "payload": {
                "call_id": "call-complete-nested-recording",
                "duration_seconds": 12,
                "recording": {
                    "url": "/v1/calls/call-complete-nested-recording/recording"
                },
            },
        },
    )

    assert response.status_code == 200
    assert recording_pipeline.processed == [
        (
            "call-complete-nested-recording",
            "https://api.voicebip.com/v1/calls/call-complete-nested-recording/recording",
            {"Authorization": "Bearer pk_live_test"},
        )
    ]


async def test_completed_call_queues_authenticated_recording_once(client, recording_pipeline):
    payload = {
        "event_id": "evt-complete",
        "event_type": "call.completed",
        "channel": "voice",
        "from": "+2348000000000",
        "payload": {
            "call_id": "call-complete",
            "status": "completed",
            "duration_seconds": 12,
            "direction": "inbound",
            "recording_url": "/v1/calls/call-complete/recording",
        },
    }

    first = await post_signed(client, payload)
    second = await post_signed(client, payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert recording_pipeline.prepared == ["call-complete"]
    assert recording_pipeline.processed == [
        (
            "call-complete",
            "https://api.voicebip.com/v1/calls/call-complete/recording",
            {"Authorization": "Bearer pk_live_test"},
        )
    ]


async def test_completed_call_uses_session_when_caller_number_is_omitted(
    client, recording_pipeline
):
    await post_signed(
        client,
        {
            "event_id": "evt-start-with-caller",
            "event_type": "call.initiated",
            "channel": "voice",
            "from": "+2348000000000",
            "payload": {
                "call_id": "call-complete-without-caller",
                "from_number": "+2348000000000",
            },
        },
    )

    response = await post_signed(
        client,
        {
            "event_id": "evt-complete-without-caller",
            "event_type": "call.completed",
            "channel": "voice",
            "payload": {
                "call_id": "call-complete-without-caller",
                "duration_seconds": 12,
                "recording_url": "/v1/calls/call-complete-without-caller/recording",
            },
        },
    )

    assert response.status_code == 200
    assert recording_pipeline.prepared == ["call-complete-without-caller"]


async def test_recording_credentials_are_limited_to_voicebip_api_host(
    client, recording_pipeline
):
    response = await post_signed(
        client,
        {
            "event_id": "evt-external-recording",
            "event_type": "call.completed",
            "channel": "voice",
            "from": "+2348000000000",
            "payload": {
                "call_id": "call-external-recording",
                "duration_seconds": 12,
                "from_number": "+2348000000000",
                "recording_url": "https://recordings.example/audio.wav",
            },
        },
    )

    assert response.status_code == 200
    assert recording_pipeline.processed == [
        (
            "call-external-recording",
            "https://recordings.example/audio.wav",
            {},
        )
    ]


async def test_inbound_sms_is_accepted_once_and_acknowledged(client, sms_service):
    payload = {
        "event_id": "evt-sms-received",
        "event_type": "message.received",
        "channel": "sms",
        "agent_id": "agt-test",
        "number": "+2342013502017",
        "from": "+2348000000000",
        "payload": {
            "message_id": "msg-inbound-001",
            "body": "There is a fire at Balogun Market",
            "encoding": "GSM-7",
        },
    }

    first = await post_signed(client, payload)
    second = await post_signed(client, payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert sms_service.reports == [
        {
            "message_id": "msg-inbound-001",
            "agent_id": "agt-test",
            "sender_number": "+2348000000000",
            "recipient_number": "+2342013502017",
            "body": "There is a fire at Balogun Market",
        }
    ]
    assert len(sms_service.acknowledgements) == 1


async def test_sms_delivery_receipt_updates_acknowledgement(client, sms_service):
    response = await post_signed(
        client,
        {
            "event_id": "evt-sms-delivered",
            "event_type": "message.dlr",
            "channel": "sms",
            "agent_id": "agt-test",
            "payload": {
                "message_id": "msg-ack-001",
                "status": "DELIVRD",
            },
        },
    )

    assert response.status_code == 200
    assert sms_service.delivery_receipts == [("msg-ack-001", "DELIVRD")]


async def test_invalid_sms_does_not_claim_event_id(client, sms_service):
    payload = {
        "event_id": "evt-sms-corrected",
        "event_type": "message.received",
        "channel": "sms",
        "agent_id": "agt-test",
        "number": "+2342013502017",
        "from": "+2348000000000",
        "payload": {"message_id": "msg-corrected", "body": ""},
    }

    invalid = await post_signed(client, payload)
    payload["payload"]["body"] = "Security emergency near the station"
    corrected = await post_signed(client, payload)

    assert invalid.status_code == 400
    assert corrected.status_code == 200
    assert len(sms_service.reports) == 1


async def test_invalid_signature_is_rejected(client):
    response = await client.post(
        "/webhooks/voicebip",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Voicebip-Timestamp": str(int(time.time())),
            "X-Voicebip-Signature": "sha256=invalid",
        },
    )

    assert response.status_code == 401
