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
- later local/cloud LLM assistance

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

## Current test baseline

Latest known checkpoint:

```text
python3 -m pytest
264 passed
0 failed
```

Warnings from `pytest-asyncio` deprecations may exist and are pre-existing unless new warnings appear.

## Important constraints

Do not add unless the active phase explicitly requires it:

- LLM calls
- agents
- embeddings
- vector DB
- RAG
- external APIs
- Google Calendar sync
- file watchers
- dashboard write routes
- new dependencies

## Security notes

- Telegram write commands must remain allowlist-protected.
- Dashboard is read-only unless auth or disabled-by-default write flag exists.
- `.env` must not be tracked.
- Secrets must never be committed.
- SQL identifier construction must be validated.

## Recommended next phase

If Phase 6 is not complete:

```text
Implement Phase 6 — Notes + Files Foundation.
```

If Phase 6 is complete:

```text
Implement Phase 6.5 — Developer Code Map.
```

Then:

```text
Phase 7 — Local LLM over selected notes.
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
