# Post-MVP Phase 12 — Production Hardening

## Status

Post-MVP optional.

## Goal

Make Atenas safe and reliable outside a local-only environment.

## In scope

- API authentication
- dashboard auth
- backup/restore
- structured logging
- error monitoring
- deployment docs
- Docker hardening
- security review
- secret management
- rate limiting if needed

## Mandatory if exposed publicly

If Atenas is deployed to a VPS or public URL, implement:

- dashboard auth
- API key/session auth
- HTTPS
- secret management
- no `.env` in git
- least-privilege deployment

## Exit criteria

Phase 12 is complete when Atenas can be safely deployed beyond local-only use.
