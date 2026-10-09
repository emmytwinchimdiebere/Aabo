# Operations

## Service startup

1. Confirm `.env` contains a non-default phone hash salt and the public HTTPS base URL.
2. Start the API and verify `GET /health` through the public origin.
3. Start the dispatcher console and confirm its connection indicator is green.
4. Place a controlled test call and verify the complete incident lifecycle.

## Dependency checks

Before an operational session, verify:

- the voice number accepts calls and reaches the configured callback;
- N-ATLAS accepts a known audio sample;
- the secondary transcription path is available;
- NIPOST responds within the configured timeout;
- the local postcode cache contains the expected operating areas;
- WebSocket events reach the console;
- HTTP incident refresh remains available.

## Failure behavior

- Never discard a call because transcription, location, or verification confidence is low.
- Mark the incident with its actual processing source and degraded fields.
- Keep provider credentials and signed media URLs out of logs.
- Prefer a partial incident visible to a dispatcher over an invisible pipeline failure.

## Incident data

Use synthetic data during development. If real caller data enters a non-production environment, stop processing, restrict access to the affected files, and follow the project's data-removal procedure before resuming work.

