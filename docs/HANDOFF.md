# Atenas Handoff - 2026-05-18

This handoff reflects the local state after pulling GitHub `origin/main` on
2026-05-18.

## Repository State

- Branch: `main`
- HEAD: `cb72413` (`Merge pull request #8 from NathanLCR/claude/compassionate-hawking-f6b968`)
- Remote status: aligned with `origin/main`
- Untracked local state: `.claude/`
- Runtime/ignored local state may exist: `.venv/`, `data/`, `logs/`,
  `.pytest_cache/`, `__pycache__/`, `.DS_Store`

During the pull, a stale `.git/index.lock`/partial worktree update occurred.
The checkout was recovered by aligning `main` to `origin/main`; the versioned
tree is now clean except for local `.claude/`.

## Verification

Dependencies were synced in a temporary Python 3.11 venv and the full suite was
run:

```bash
/private/tmp/atenas-test-venv/bin/pip install -r requirements.txt
/private/tmp/atenas-test-venv/bin/pytest -q
```

Result:

```text
328 passed
```

Notes:

- `jinja2==3.1.6` is now required for dashboard templates.
- The repo-local `.venv` still appears to use Python 3.13 from the previous
  environment. Prefer recreating it with Python 3.11 before new work.
- `pytest-asyncio` emits the known `asyncio_default_fixture_loop_scope`
  deprecation warning.

## Completed Scope

The implementation is no longer just the original Phase 1 skeleton.

Completed:

- Phase 0 - spec foundation
- Phase 1 - core FastAPI/SQLite/app skeleton
- Phase 2 - Telegram bot + dashboard foundation
- Phase 3 - academic/work scheduling + availability
- Phase 4 - deterministic study planner
- Phase 5 - controlled data input/editing + imports
- Phase 6 - notes + files foundation
- Phase 6.5 - developer code map
- Phase 7 - local LLM over selected notes

Key implemented areas:

- `app/main.py` lazily builds the ASGI app and starts Telegram only when a token
  is configured.
- `app/bot.py` contains allowlisted Telegram commands for status, scheduling,
  planning, academic data input, notes/files/search, and selected-note LLM
  actions.
- `app/dashboard.py` exposes read-only dashboard pages.
- `core/academic/` owns modules, classes, shifts, assignments, availability,
  deterministic plans, and imports.
- `core/knowledge/` owns notes, file metadata, note-file links, validation, and
  deterministic keyword search.
- `core/llm/` owns local Ollama-compatible selected-note actions.
- `docs/code-map/` gives future agents a compact architecture map.

## Current Routes

API:

- `GET /health`
- `GET /status`
- `GET /skills`

Dashboard:

- `GET /dashboard/`
- `GET /dashboard/week`
- `GET /dashboard/deadlines`
- `GET /dashboard/plan`
- `GET /dashboard/data`
- `GET /dashboard/notes`
- `GET /dashboard/files`
- `GET /dashboard/search`
- `GET /dashboard/logs`
- `GET /dashboard/llm`

## Current Telegram Surface

Status:

- `/ping`
- `/status`
- `/skills`

Schedule/planning:

- `/today`
- `/week`
- `/deadlines`
- `/availability`
- `/plan`
- `/study`

Controlled data input/editing:

- `/add_module`
- `/add_class`
- `/add_shift`
- `/add_assignment`
- `/set_status`
- `/set_hours`
- `/modules`
- `/classes`
- `/shifts`
- `/assignments`

Knowledge:

- `/add_note`
- `/notes`
- `/note`
- `/archive_note`
- `/add_file`
- `/files`
- `/search`
- `/link_note_file`

Selected-note local LLM:

- `/summarize_note`
- `/explain_note`
- `/questions_note`
- `/flashcards_note`
- `/rewrite_note`

## Next Phase

Proceed with **Phase 8 - Controlled Retrieval/RAG Foundation**.

Read first:

1. `docs/phases/phase-08-controlled-rag-foundation.md`
2. `docs/code-map/architecture-map.md`
3. `docs/code-map/core-knowledge.md`
4. `docs/code-map/telegram.md`
5. `docs/code-map/dashboard.md`
6. `docs/codex/MASTER_CODEX_HANDOFF.md`

Recommended start:

1. Recreate `.venv` with Python 3.11.
2. Run `pytest -q` before changes.
3. Create a branch, for example `codex/phase-08-controlled-rag`.
4. Implement a small retrieval layer over registered notes/files only.
5. Keep embeddings/LLM calls controlled and local.
6. Add source display and no-source fallback before any answer generation.
7. Add tests for chunking, indexing, retrieval, archived exclusion, source
   display, no-source fallback, Telegram commands, and dashboard read-only view
   if added.

## Phase 8 Boundaries

In scope:

- Retrieval over registered notes/file text
- Chunking selected notes and optionally registered text files
- Local embeddings or a SQLite-friendly retrieval strategy
- Explicit source IDs in answers
- Telegram commands for controlled question answering
- Optional read-only dashboard retrieval page

Out of scope:

- Autonomous agents
- Web search
- Cloud fallback
- Automatic filesystem ingestion
- OCR
- Complex PDF parsing unless separately scoped
- Dashboard write routes without auth

## Useful Commands

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload
docker-compose up
```
