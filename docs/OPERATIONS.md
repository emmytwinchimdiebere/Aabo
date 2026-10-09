# Operations

## Service startup

1. Confirm `.env` contains a non-default phone hash salt and the public HTTPS base URL.
2. Start the API and verify `GET /health` through the public origin.
3. Start the dispatcher console and confirm its connection indicator is green.
4. Place a controlled test call and verify the complete incident lifecycle.

Mount durable storage at the directory configured by `RECORDING_STORAGE_PATH`.
For Railway, use a service volume mounted at `/data` and set
`DATABASE_PATH=/data/aabo.db` and `RECORDING_STORAGE_PATH=/data/recordings`.
Without a mounted volume, incident records and recordings can be lost on a
redeploy or container replacement.

## VoiceBIP readiness

Before assigning the public number to a test caller, confirm:

- `BASE_URL` is the deployed HTTPS origin, not the placeholder from `.env.example`;
- `VOICEBIP_API_KEY` and `VOICEBIP_SIGNING_SECRET` are present only in the deployment environment;
- the agent webhook URL is `{BASE_URL}/webhooks/voicebip`;
- the VoiceBIP agent is active and assigned to the provisioned number;
- the assigned number reports `sms` in its channels before advertising SMS intake;
- recording is enabled with the required consent prompt;
- `api.voicebip.com` is allowed for recording downloads;
- a signed `call.initiated` event returns HTTP 200;
- a completed test call creates exactly one transcript even if the event is retried;
- a controlled inbound SMS creates one text report, one acknowledgement, and a delivery receipt.

VoiceBIP webhook processing returns `401` for an invalid or stale signature and `503` when no signing secret is configured. Do not disable verification to work around either response.

## Dependency checks

Before an operational session, verify:

- the voice number accepts calls and reaches the configured callback;
- the provider dashboard and API both report recording as enabled;
- N-ATLAS accepts a known audio sample;
- the dispatcher can play the original recording through the Aabo recording endpoint;
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
