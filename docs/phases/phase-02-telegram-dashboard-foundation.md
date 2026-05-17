# Phase 2 — Telegram + Dashboard Foundation

## Status

Complete.

## Final checkpoint

Phase 2 completed with:

- Telegram bot with allowlist
- `/ping`
- `/status`
- `/skills`
- unknown-command handling
- FastAPI-controlled bot lifecycle
- read-only `/dashboard/`
- read-only `/dashboard/logs`
- Jinja dashboard
- `jinja2==3.1.6`
- all tests passing at checkpoint

## Goal

Add user-facing surfaces without adding complex product logic.

## In scope

### Telegram

- allowlist protection
- basic commands
- bot lifecycle controlled by FastAPI
- clean startup/shutdown

### Dashboard

- read-only status page
- read-only logs page
- Jinja templates
- no dashboard writes

## Out of scope

- scheduling
- planner
- CRUD input
- notes/files
- LLM
- RAG

## Security rule

Telegram commands that mutate data must be allowlist-protected in future phases.

Dashboard remains read-only until authentication or feature flags exist.

## Tests

Add tests for:

- bot command registration
- allowlist behavior
- basic commands
- unknown command
- dashboard pages
- FastAPI lifecycle

## Exit criteria

Phase 2 is complete when Telegram and dashboard exist as stable shells and all tests pass.
