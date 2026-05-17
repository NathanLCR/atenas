# Phase 1 — Core App Skeleton

## Status

Complete.

## Goal

Create the minimal working application foundation.

## Scope

Implement:

- FastAPI app
- settings/config layer
- SQLite database bootstrap
- test structure
- basic health/status route
- simple project layout
- deterministic local runtime

## In scope

- app startup
- database initialization
- settings loading
- basic logging
- baseline tests
- local development workflow

## Out of scope

- Telegram bot
- dashboard UI
- scheduling logic
- planner logic
- LLM
- RAG
- notes/files

## Architecture expectation

Keep business logic out of FastAPI routes.

Preferred direction:

```text
FastAPI route -> service -> repository/database
```

## Tests

Add tests for:

- app startup
- health/status route
- settings
- database initialization
- regression-safe baseline

## Exit criteria

Phase 1 is complete when the app can start, initialize SQLite, and pass the baseline test suite.
