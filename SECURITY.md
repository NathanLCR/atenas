# Security Policy

Atenas is a local-running study assistant. It is not designed to be exposed to
the public internet; the API and dashboard bind to `127.0.0.1` by default.

## Reporting a vulnerability

Please report suspected vulnerabilities privately using GitHub's
[private vulnerability reporting](../../security/advisories/new) for this
repository. Do not open a public issue for security problems, and never include
real bot tokens, API keys, or `.env` contents in a report.

You can expect an initial response within a few days. Fixes are released on
`main` and noted in `CHANGELOG.md`.

## Threat model

The threat model, trust boundaries, and tool-safety rules are documented in
[docs/SECURITY.md](docs/SECURITY.md).
