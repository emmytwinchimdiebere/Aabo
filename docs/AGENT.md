# Aabo emergency agent

Aabo owns the conversational decisions used during a VoiceBIP call. VoiceBIP is
the telephony and speech transport: it transcribes each caller turn, sends the
text to the signed BYOM webhook, synthesizes Aabo's response, and plays it to
the caller.

## Personality

Aabo is calm, direct, respectful, and safety-oriented. It asks one short
question at a time, does not promise that responders have been dispatched, and
does not discard a report merely because a location or transcription has low
confidence.

After the incident tool succeeds, Aabo gives one short reassurance: the report
is with the dispatcher, the caller should stay calm, and they should move to
safety if possible. The call then ends immediately to avoid unnecessary call
cost and to keep the line available.

## Language selection

The agent supports English (`en`), Yoruba (`yo`), Hausa (`ha`), and Igbo (`ig`).
A caller can say a language name explicitly. If the caller immediately reports
an emergency, the agent scores language-specific phrases and continues when one
language has a clear lead. Ambiguous input produces a short clarification
instead of an unsafe guess. The selected language is stored on the call session
and is also used to select the post-call N-ATLaS model.

VoiceBIP performs speech recognition before a BYOM turn reaches Aabo. The public
number therefore uses language-specific VoiceBIP agents behind first-utterance
routing. Saying `one`, `two`, `three`, or `four` routes the call to an English,
Yoruba, Hausa, or Igbo speech profile respectively. Every profile points to the
same Aabo webhook and state machine; the agent ID supplies a trusted language
hint so a poor transcription of the selection does not silently switch the
conversation back to English. N-ATLaS processes the authenticated call recording
after the call and provides the primary stored transcript, with Whisper as the
fallback.

## Location conversation

Location is collected before the emergency description when it was not already
present in the first utterance. The caller may provide a street, junction,
market, school, hospital, building, landmark, town, or postcode.

1. Broad answers such as a state or major city prompt for a nearby street or
   landmark.
2. If speech recognition splits an address across two short turns, Aabo keeps
   the first fragment and combines it with the second. After one request for
   more detail, a non-empty low-confidence location is read back for explicit
   confirmation instead of trapping the caller in a repetition loop.
3. Specific answers are normalized into a location candidate with a source and
   confidence.
4. Aabo reads the candidate back and asks the caller to confirm or correct it.
5. A confirmed candidate is stored with the incident as caller-confirmed; it is
   not represented as GPS-verified.
6. Aabo then reads back the emergency description. The caller can confirm it,
   reject it and try again, or speak a replacement description directly.

The `SpokenLocationResolver` is the provider-independent boundary for this
logic. A NIPOST-backed resolver can later enrich the same candidate with a
postcode, canonical address, and coordinates without changing the conversation
or VoiceBIP adapter.

## Tools

`CreateEmergencyIncidentTool` is the first allowlisted agent tool. It runs only
after both the location and emergency description have been confirmed. It
converts the confirmed call state into an incident for dispatcher review and is
idempotent per call session. The tool classifies the report into fire, medical,
security, accident, or other; records location provenance and confidence; and
returns the existing incident when the same call is submitted twice.

Each invocation writes a structured audit log containing only the tool name,
session ID, and incident ID. Emergency text is not copied into application logs.

Tool implementations own validation and persistence. Conversational text never
executes arbitrary functions or SQL.

## Conversation state

The `agent_conversations` table stores a small explicit state machine:

- `start`
- `awaiting_location`
- `confirming_location`
- `awaiting_emergency`
- `confirming_emergency`
- `complete`

Persisted state keeps the flow deterministic across VoiceBIP turn requests and
makes each decision auditable. It also keeps the webhook comfortably inside
VoiceBIP's latency budget without depending on a remote general-purpose model.
