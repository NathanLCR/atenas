# Atenas — Master Codex Handoff

## Project identity

Name: Atenas  
Repo/framework name: `atenas-core`

Atenas is a local-first AI study operating system for working students.

It helps manage:

- classes
- work shifts
- assignments
- deadlines
- study plans
- notes
- files
- local LLM assistance
- controlled source-grounded retrieval

## Build method

Spec-driven development.

Each phase should follow:

```text
read spec -> inspect repo -> implement minimal scope -> add tests -> run full tests -> report summary
```

## Current completed phases

- Phase 0 — Spec foundation
- Phase 1 — Core app skeleton
- Phase 2 — Telegram + dashboard foundation
- Phase 3 — Academic/work scheduling
- Phase 4 — deterministic study planner
- Phase 5 — controlled data input/editing
- Phase 6 — notes + files foundation
- Phase 6.5 — developer code map
- Phase 7 — local LLM over selected notes
- Phase 8 — controlled retrieval/RAG foundation

## Current test baseline

Latest verified checkpoint after Phase 8 polish on 2026-05-18:

```text
.venv/bin/pytest -q
349 passed
```

Warnings from `pytest-asyncio` deprecations may exist and are pre-existing unless new warnings appear.

## Phase 8 summary

Phase 8 adds controlled local retrieval over registered notes and supported text files.

Implemented:

- `core/retrieval/` package for deterministic chunking, SQLite-backed lexical retrieval, prompt construction, and source-grounded answers.
- `retrieval_chunks` SQLite table and indexes.
- Telegram commands:
  - `/ask_notes`
  - `/ask_note`
  - `/sources`
- Dashboard route:
  - `/dashboard/retrieval`
- Read-only dashboard retrieval filters:
  - `module`
  - `assignment`
- No-source fallback when no registered source supports the question.
- Source display even when local Ollama is unavailable after sources are found.

## Important constraints

Do not add unless the active phase explicitly requires it:

- uncontrolled LLM features
- agents
- cloud fallback
- external APIs
- Google Calendar sync
- file watchers
- dashboard write routes
- new dependencies

Controlled RAG now exists, but it is limited to registered local notes/files, local Ollama, explicit sources, and the no-source fallback. Do not add web search, automatic filesystem ingestion, OCR/PDF parsing, cloud fallback, or a vector database unless a later spec explicitly scopes it.

## Security notes

- Telegram write commands must remain allowlist-protected.
- Dashboard is read-only unless auth or disabled-by-default write flag exists.
- `.env` must not be tracked.
- Secrets must never be committed.
- SQL identifier construction must be validated.

## Recommended next work

```text
Define the next post-MVP phase, or continue Phase 8 polish only within the local-only controlled retrieval boundaries.
```

## Final response format for every phase

```markdown
# Phase X implementation summary

## Changed
- ...

## Added
- ...

## Tests
- Command:
- Total:
- Passed:
- Failed:
- Warnings:

## Commands added
- ...

## Dashboard added
- ...

## Notes
- ...

## Next recommended phase
- ...
```
