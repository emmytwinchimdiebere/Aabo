# Architecture

## System shape

Aabo is a modular monolith with two deployable applications:

- a FastAPI service responsible for provider callbacks, processing, and persistence;
- a React dispatcher console responsible for presenting incidents and source evidence for human review.

SQLite is the initial datastore. Ordered SQL migrations preserve a clear path to a server database if traffic or operational requirements outgrow a single-node deployment.

## Backend boundaries

| Layer | Responsibility | Must not contain |
|---|---|---|
| `api` | HTTP contracts, provider field mapping, response codes | SQL or provider-independent decisions |
| `services` | Application workflows and orchestration | Framework-specific request objects |
| `repositories` | Persistence queries and transaction boundaries | HTTP response behavior |
| `core` | Configuration, logging, shared runtime concerns | Domain workflows |
| `migrations` | Versioned schema changes | Application code |

The boundaries are intentionally lightweight. They make external integrations testable without introducing distributed-system overhead.

## Call ingestion sequence

1. A voice provider sends call metadata to its provider-specific HTTP endpoint.
2. The boundary adapter validates the request, normalizes provider fields, and delegates to `VoiceIntakeService`.
3. The service hashes the caller number with a configured secret and creates a call session with English as the safe default.
4. Aabo accepts an explicit English, Yoruba, Hausa, or Igbo selection. A clear first-sentence report can select the language automatically; ambiguous speech receives a short clarification.
5. Aabo requests the easiest available location signal, asks for a street or landmark when the answer is too broad, and reads the candidate back for caller confirmation.
6. Aabo reads the emergency description back and accepts confirmation or a correction. The allowlisted incident tool runs only after both location and emergency details are confirmed.
7. The provider records the call after obtaining caller consent.
8. Recording metadata transitions the session to `recording_ready`; the callback is acknowledged and ingestion continues as a background task.
9. The downloader validates the URL, redirect targets, content type, response size, and timeout before accepting audio. Authentication is never forwarded to a different redirect host. Accepted audio is copied to Aabo-controlled recording storage and linked to the incident; the temporary provider URL is discarded.
10. The selected N-ATLaS language model processes the audio first. Whisper is attempted when that model is unavailable; otherwise the record is marked for manual transcription.
11. Transcription provenance and processing state are persisted before classification begins.
12. N-ATLaS extracts only location details present in the transcript and returns an unverified candidate for caller correction. Browser coordinates can accompany that candidate.
13. NIPOST enrichment and device-location comparison can add stronger location signals without replacing caller confirmation. The production client remains disabled until approved API access and the official contract are configured.
14. The incident becomes visible in the dispatcher console for human review. The console currently refreshes over HTTP; authenticated decision recording is an explicit roadmap item.

### Provider adapters

- VoiceBIP sends lifecycle events and BYOM conversation turns to `POST /webhooks/voicebip`. Requests require a fresh timestamp and valid HMAC signature. Event IDs are claimed once so provider retries do not enqueue a recording twice.
- VoiceBIP speech profiles can route a caller's language selection to the same BYOM webhook. Configured agent IDs become language hints for Aabo's provider-independent conversation state. A language is not advertised as live-call ready until its provider speech profile has passed an end-to-end call test.
- Africa's Talking uses `POST /voice/incoming`, `/voice/language`, `/voice/recording`, and `/voice/end`. Its XML and form fields are confined to the API layer.
- Both adapters share session persistence, media validation, transcription, and downstream incident processing.
- The Aabo agent design, language policy, location state machine, and tool boundary are documented in [AGENT.md](./AGENT.md).

## SMS ingestion sequence

1. VoiceBIP sends a signed `message.received` event to the existing webhook.
2. The API validates all required identifiers and the message size before claiming the event ID.
3. The sender number is transformed with the same HMAC-SHA-256 policy used for callers.
4. The text report is persisted directly; speech transcription is intentionally skipped.
5. A short acknowledgement is queued through the VoiceBIP Messages API after the webhook has been accepted.
6. `message.dlr` events update the acknowledgement delivery status.
7. Downstream incident composition consumes the normalized report text regardless of whether it originated as audio or SMS.

## Dependency resilience

| Capability | Primary | Secondary path |
|---|---|---|
| Transcription | N-ATLAS | Whisper, then manual transcript |
| Location extraction | Language model | Deterministic street and landmark rules |
| Postcode resolution (planned) | NIPOST API | Locally cached postcode data |
| Console updates | Periodic HTTP refresh | Manual browser refresh |
| Location signal | Device coordinates | Spoken location |

Failures must be visible in the incident record. A degraded result can still be useful to a dispatcher; a hidden failure cannot.

## Data handling

- Phone numbers are transformed with HMAC-SHA-256 before persistence.
- Signed provider URLs are validated and held only for the duration of ingestion.
- Provider API authorization is sent only to the configured recording host and removed on cross-host redirects.
- VoiceBIP webhook signatures are checked against the exact raw request body before JSON parsing.
- Audio and database files are excluded from version control.
- Raw N-ATLaS output and caller-corrected text are stored separately so dispatchers can audit proper-noun corrections against the original audio.
- Every incident reaches human review regardless of automated confidence.
- Production configuration rejects an insecure base URL or default hashing secret.

## Open design decisions

1. Define the authenticated mechanism that associates device coordinates with a voice session.
2. Resolve spoken and device locations to a shared coordinate/postcode representation before comparison.
3. Confirm whether the voice provider supports streaming audio; otherwise expose processing stages rather than word-level streaming.
4. Define retention periods for audio, transcripts, caller hashes, and incident records before operational deployment.
