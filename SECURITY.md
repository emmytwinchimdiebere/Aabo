# Security Policy

## Reporting a vulnerability

Do not open a public issue for vulnerabilities involving credentials, caller identity, recordings, precise locations, or unauthorized incident access. Report them privately to the repository maintainers with reproduction steps and the affected version.

## Sensitive data

The following data must never be committed:

- API keys, access tokens, or webhook secrets;
- raw caller phone numbers;
- signed recording URLs or downloaded caller audio;
- real transcripts or incident locations;
- local SQLite database files.

Use synthetic fixtures in tests and documentation.

## Deployment boundary

The current service does not include operator authentication or authorization. It must remain on a controlled network until those controls, transport security, audit logging, and a retention policy are implemented.

