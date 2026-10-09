# Aabo roadmap

## Vision

Every Nigerian, in any language and on any phone, should be able to reach emergency support quickly and be understood accurately.

The roadmap separates working product capabilities from integrations that still depend on carrier, government, or emergency-centre access. An unchecked item is not advertised as live.

## Phase 1 — Working foundation

- [x] Inbound voice through **+234 201 350 2017**
- [x] Stateful Aabo conversation behind a signed VoiceBIP BYOM webhook
- [x] Nigerian English, Yoruba, Hausa, and Igbo language selection
- [x] Spoken-location capture and explicit caller confirmation
- [x] Emergency-description read-back and confirmation before submission
- [x] Allowlisted, idempotent incident-creation tool
- [x] N-ATLAS recording transcription for four supported languages
- [x] Browser voice reporting with transcript and address correction
- [x] Dispatcher incident queue with original-audio playback
- [x] Automated backend tests and frontend production build in CI

## Activation gates

These integrations exist in code or behind a service boundary but are not described as live until the external dependency is ready.

- [ ] Enable SMS on the public carrier number and validate inbound and delivery-receipt events
- [ ] Obtain NIPOST address-resolution scopes and validate canonical postcode responses
- [ ] Complete provider-side speech profiles for every supported live-call language
- [ ] Add dispatcher authentication, authorization, and a formal retention policy
- [ ] Exercise recovery paths in a controlled end-to-end operational test

## Phase 2 — Access and pilot readiness

- [ ] USSD fallback for low-connectivity and non-smartphone users
- [ ] WhatsApp intake for typed reports, images, and location pins
- [ ] Accessible web chat for deaf and hard-of-hearing callers
- [ ] Verified local postcode cache for degraded NIPOST operation
- [ ] Realtime console updates with an HTTP polling fallback
- [ ] Dispatcher acknowledgement, assignment, and resolution audit trail
- [ ] Multi-state pilot with participating emergency coordination centres

## Phase 3 — Emergency-network integration

- [ ] Direct CAD and responder-system adapters
- [ ] Integration with an official national emergency number, subject to government and carrier approval
- [ ] Multi-region deployment with encrypted managed storage
- [ ] Operational analytics for response coverage and capacity planning
- [ ] Native responder application where existing CAD clients are unavailable

## Engineering rule

A capability moves to “working foundation” only when it includes persistence, operator visibility, failure handling, tests, and documentation. External access or a partial adapter alone does not make a channel live.
