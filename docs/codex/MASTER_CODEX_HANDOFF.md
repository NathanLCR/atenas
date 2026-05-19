# Atenas — Master Codex Handoff

> Historical handoff. The current product direction changed on 2026-05-19 to a
> local-running, Telegram-first LLM tool agent. For current work, read
> `docs/HANDOFF.md` and `docs/HANDOFF_NL_INTERFACE.md` first.

## Project identity

Name: Atenas  
Repo/framework name: `study-agent-cd`

Atenas is a local-running, Telegram-first AI study assistant for working students.

It helps manage:

- classes
- work shifts
- assignments
- deadlines
- study plans
- notes
- files
- LLM assistance through controlled tools
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
- Phase 9 — notifications + reminders

## Historical test baseline

This section intentionally avoids carrying a numeric pass count. Re-run tests
in the current workspace before implementation work.

Warnings from `pytest-asyncio` deprecations may exist and are pre-existing unless new warnings appear.

## Phase 9 summary

Phase 9 adds proactive Telegram notifications using asyncio background tasks (no new dependencies).

Implemented:

- `core/notifications/` package: `DeadlineAlert`, `StudyBlockReminder`, `OverdueAlert` models and `NotificationService`.
- Asyncio background loops for: daily deadline alerts (08:00), overdue checks (22:00), 15-minute study-block poll, and Sunday weekly review (18:00).
- Graceful task cancellation on bot shutdown.
- Telegram command:
  - `/reminders`
- Config settings:
  - `NOTIFICATIONS_ENABLED` (default: `true`)
  - `NOTIFICATIONS_CHAT_ID` (required for proactive pushes)
  - `DEADLINE_ALERT_HOURS` (default: `72`)

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
- autonomous agents outside the approved Telegram tool-agent flow
- cloud fallback
- external APIs
- Google Calendar sync
- file watchers
- dashboard write routes
- new dependencies

Controlled RAG now exists, but it is limited to registered local notes/files, local Ollama, explicit sources, and the no-source fallback. Do not add web search, automatic filesystem ingestion, OCR/PDF parsing, cloud fallback, or a vector database unless a later spec explicitly scopes it.

## Security notes

- Telegram commands, plain messages, LLM calls, and tools must remain allowlist-protected.
- Dashboard/API surfaces are local-only by default.
- Dashboard is read-only unless auth or disabled-by-default write flag exists.
- `.env` must not be tracked.
- Secrets must never be committed.
- SQL identifier construction must be validated.

## Recommended next work

```text
Telegram LLM Tool Interface.
See docs/HANDOFF_NL_INTERFACE.md and docs/phases/phase-natural-language-interface.md.
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
