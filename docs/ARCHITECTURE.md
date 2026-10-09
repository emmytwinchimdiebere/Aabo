# Architecture

## System shape

Aabo 112 is a modular monolith with two deployable applications:

- a FastAPI service responsible for provider callbacks, processing, persistence, and realtime events;
- a React dispatcher console responsible for presenting incidents and recording human decisions.

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

1. Africa's Talking sends call metadata to `POST /voice/incoming`.
2. The API normalizes provider field names and delegates to `VoiceIntakeService`.
3. The service hashes the caller number with a configured secret and creates the call session.
4. The API returns provider XML containing instructions and a session-bound recording callback.
5. The provider sends recording metadata to `POST /voice/recording`.
6. The session transitions to `recording_ready` and the ingestion pipeline receives the signed audio URL.
7. Transcription, classification, location resolution, and verification compose an incident.
8. The incident is persisted and published to the dispatcher console.
9. A human dispatcher records the final decision.

## Dependency resilience

| Capability | Primary | Secondary path |
|---|---|---|
| Transcription | N-ATLAS | Whisper, then manual transcript |
| Location extraction | Language model | Deterministic street and landmark rules |
| Postcode resolution | NIPOST API | Locally cached postcode data |
| Console updates | WebSocket | Periodic HTTP refresh |
| Location signal | Device coordinates | Spoken location |

Failures must be visible in the incident record. A degraded result can still be useful to a dispatcher; a hidden failure cannot.

## Data handling

- Phone numbers are transformed with HMAC-SHA-256 before persistence.
- Signed provider URLs are held only for the duration of ingestion.
- Audio and database files are excluded from version control.
- Every incident reaches human review regardless of automated confidence.
- Production configuration rejects an insecure base URL or default hashing secret.

## Open design decisions

1. Define the authenticated mechanism that associates device coordinates with a voice session.
2. Resolve spoken and device locations to a shared coordinate/postcode representation before comparison.
3. Confirm whether the voice provider supports streaming audio; otherwise expose processing stages rather than word-level streaming.
4. Define retention periods for audio, transcripts, caller hashes, and incident records before operational deployment.

