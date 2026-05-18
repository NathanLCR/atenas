# Atenas Core

Atenas is a local-first AI study operating system for working students. It now
includes the core app skeleton, Telegram command surface, read-only dashboard,
academic scheduling, deterministic planning, notes/files/search, code-map docs,
and local LLM actions over explicitly selected notes.

## Current State

Latest verified local baseline, after pulling `origin/main` on 2026-05-18:

- Branch: `main`
- HEAD: `cb72413`
- Tests: `328 passed`
- Next phase: Phase 8 - Controlled Retrieval/RAG Foundation

See `docs/HANDOFF.md` and `docs/codex/MASTER_CODEX_HANDOFF.md` before starting
the next implementation phase.

## Run

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

## Test

```bash
.venv/bin/pytest -q
```

## Docker

```bash
docker-compose up
```

## Main Surfaces

- API: `/health`, `/status`, `/skills`
- Dashboard: `/dashboard/`, `/dashboard/week`, `/dashboard/deadlines`,
  `/dashboard/plan`, `/dashboard/data`, `/dashboard/notes`,
  `/dashboard/files`, `/dashboard/search`, `/dashboard/logs`, `/dashboard/llm`
- Telegram: status, scheduling, planning, data input, notes/files/search, and
  selected-note local LLM commands
