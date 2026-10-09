# Contributing

Thank you for contributing to Aabo 112. Changes should be small, reviewable, and tied to an observable caller or dispatcher outcome.

## Development workflow

1. Open or select an issue with clear acceptance criteria.
2. Create a branch from `main` using `feat/`, `fix/`, `docs/`, or `chore/`.
3. Keep provider-specific behavior behind a service boundary.
4. Add or update focused tests for changed behavior.
5. Run the quality checks documented in `README.md`.
6. Open a pull request using the repository template.

## Commit messages

Use short imperative messages with a conventional prefix:

```text
feat: accept voice recording callbacks
fix: preserve session state when callbacks are retried
docs: document postcode cache refresh procedure
```

## Engineering principles

- The dispatcher remains the final decision-maker.
- External dependencies require an observable failure state and fallback.
- Provider payloads are normalized at the API boundary.
- Domain behavior belongs in services, not route handlers.
- SQL access belongs in repositories or migrations.
- Secrets, caller numbers, audio, and precise real-world locations must not enter Git history.
- Prefer the smallest change that completes an end-to-end capability.

## Pull requests

Explain the behavior changed, the reason for the change, and how it was verified. Include sanitized screenshots or logs when they help reviewers. Call out schema, environment-variable, provider-contract, or operator-workflow changes explicitly.

