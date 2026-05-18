# Atenas Phases Roadmap

Atenas is a local-first AI study operating system for working students.

It is being built with spec-driven development:

```text
spec -> implementation -> tests -> audit -> next phase
```

## Current Status

As of the 2026-05-18 checkpoint after pulling `origin/main`:

| Phase | Status | Summary |
|---:|---|---|
| 0 | Complete | Product definition, requirements, architecture direction |
| 1 | Complete | Core FastAPI/SQLite/app skeleton |
| 2 | Complete | Telegram bot + dashboard foundation |
| 3 | Complete | Academic/work scheduling + availability |
| 4 | Complete | Deterministic study planner |
| 5 | Complete | Controlled data input/editing + imports |
| 6 | Complete | Notes + files foundation |
| 6.5 | Complete | Developer code map |
| 7 | Complete | Local LLM over selected notes |
| 8 | Next | Controlled retrieval/RAG foundation |

Current verified test baseline:

```text
328 passed
```

## MVP target

The MVP is defined as Phases 0–8.

```text
Useful personal system: Phase 0–5
Knowledge system: Phase 0–6
AI-assisted system: Phase 0–7
RAG-enabled MVP: Phase 0–8
```

## Global constraints

Until explicitly allowed by a phase spec, do not add:

- uncontrolled LLM features
- autonomous agents
- cloud APIs
- embeddings/vector database
- RAG
- Google Calendar sync
- iCloud/Drive sync
- dashboard write routes without auth
- unnecessary dependencies

## Testing rule

Every phase must preserve all previous tests and add meaningful new tests.

Default command:

```bash
python3 -m pytest
```

## Security rule

Telegram write commands must remain allowlist-protected.

Dashboard write routes are deferred unless authentication or a disabled-by-default feature flag exists.

## Branching recommendation

Use one branch per phase:

```bash
git checkout -b phase-06-notes-files
git checkout -b phase-07-local-llm
git checkout -b ui-dashboard-refresh
```

Do not mix backend phase work with UI polish unless the spec explicitly says so.
