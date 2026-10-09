# Engineering Roadmap

The immediate objective is a complete call-to-dispatcher path. Items are ordered by dependency and operational value.

## P0 — Voice ingestion

- [x] Establish the application structure, configuration, migrations, and tests.
- [x] Accept incoming-call, recording-ready, and call-ended callbacks.
- [x] Hash caller identifiers before persistence.
- [x] Download provider audio with time, size, and content-type limits.
- [x] Integrate N-ATLAS transcription through Hugging Face Inference.
- [x] Add Whisper fallback and an explicit manual-transcription state.
- [x] Persist transcript provenance and confidence.

Exit condition: a phone call produces a stored transcript with its processing source visible.

## P0 — Incident composition

- [ ] Classify reports into medical, fire, security, accident, or other.
- [ ] Extract streets and landmarks from the transcript.
- [ ] Resolve device coordinates through NIPOST.
- [ ] Add verified postcode cache data and nearest-neighbour lookup.
- [ ] Normalize spoken and device locations before comparison.
- [ ] Calculate spoof-risk and presence scores.
- [ ] Persist a complete incident record.

Exit condition: every processed call creates an incident that is understandable without reading raw logs.

## P0 — Dispatcher workflow

- [ ] Publish incident events over WebSocket.
- [ ] List and select active incidents.
- [ ] Display transcript, language, category, postcode, confidence, and risk.
- [ ] Display incidents on an OpenStreetMap/Leaflet map.
- [ ] Record confirm and reject decisions.
- [ ] Add HTTP refresh when realtime delivery is unavailable.

Exit condition: a dispatcher can receive, inspect, and decide an incident from the console.

## P1 — Operational readiness

- [ ] Exercise each secondary dependency path.
- [ ] Add structured correlation IDs across call processing.
- [ ] Document data retention and deletion procedures.
- [ ] Add application metrics and error reporting.
- [ ] Define authentication and authorization before public deployment.

## Deferred

- Direct national shortcode integration
- CAD and responder-system integration
- SMS and USSD intake
- Multi-node deployment
- Native mobile applications
