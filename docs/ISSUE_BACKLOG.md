# Roadmap issue backlog

These issue definitions keep planned channels concrete and prevent unfinished integrations from being represented as live. Create them with the `roadmap` and `phase-2` labels.

## [Feature] USSD fallback for low-connectivity areas

**Outcome:** A caller with a basic phone can submit a short emergency report without mobile data.

**First slice:** Establish a provider session, collect language, incident type, area or landmark, and callback number, then create a visibly labeled USSD incident for dispatcher review.

**Acceptance criteria:**

- The flow completes within provider session limits.
- Partial or timed-out sessions remain visible to an operator.
- Caller identifiers follow the existing keyed-hash policy.
- A dispatcher can distinguish USSD from voice, SMS, and web reports.

## [Feature] WhatsApp integration for location pins

**Outcome:** A caller can submit text, a location pin, and optional incident media through WhatsApp.

**First slice:** Accept signed inbound text and location messages, normalize them into the incident pipeline, and expose source and consent metadata to the dispatcher.

**Acceptance criteria:**

- Webhook signatures and retries are handled safely.
- Location pins never overwrite caller-provided address text.
- Media is size-limited, scanned, and protected by the retention policy.
- Provider delivery failures are visible to operators.

## [Feature] Accessible web chat for deaf and hard-of-hearing callers

**Outcome:** A caller can complete the emergency intake without speech or audio.

**First slice:** Provide a keyboard-first conversation for language, location, emergency details, confirmation, and incident submission.

**Acceptance criteria:**

- The complete flow is usable without a mouse.
- Status changes are announced to assistive technology.
- Location and emergency details require explicit confirmation.
- The dispatcher sees the original and caller-confirmed text.

## [Integration] Direct CAD integration with emergency centres

**Outcome:** A confirmed Aabo incident can be transferred to an authorized emergency centre without manual re-entry.

**First slice:** Define a versioned adapter and exercise it against an approved test environment with synthetic incidents.

**Acceptance criteria:**

- The receiving centre formally approves the data contract and authentication method.
- Transfers are idempotent and fully audited.
- A failed transfer remains in the dispatcher queue with a retry path.
- No integration is described as operational before an end-to-end partner test.
