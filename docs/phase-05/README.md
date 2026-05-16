# Phase 5 — Controlled Data Input + Editing

## Status before Phase 5

Atenas has completed:

- Phase 1: app/database foundation
- Phase 2: Telegram + dashboard foundation
- Phase 3: academic/work scheduling foundation
- Phase 4: deterministic study planner

Audit branch:

```text
fix/audit-issues
```

Audit fixes completed:

- SQL injection risk fixed in `_ensure_column`
- Telegram token revoked
- bot lifespan cleanup improved
- SQL filtering/ordering improved
- assignment description/notes bug fixed
- invalid assignment status fallback added
- bot settings now use `context.bot_data`
- `/dashboard/plan` added
- all tests passing

Current test baseline:

```text
python3 -m pytest
116 passed
0 failed
```

Known warning noise:

```text
pytest-asyncio / Python 3.14 deprecation warnings
```

## Phase 5 goal

Phase 5 makes Atenas usable without manually editing SQLite.

The system should allow controlled creation and editing of:

- modules
- class sessions
- work shifts
- assignments
- assignment status
- completed hours

It should also support simple deterministic imports from local fixture files.

## Product outcome

After Phase 5, the user should be able to maintain Atenas data through safe interfaces.

Atenas should answer:

> How do I add, edit, and update the data needed by the planner?

## Core principle

Phase 5 is still deterministic.

No LLMs.
No agents.
No natural-language parsing.
No external APIs.
No calendar sync.

## Main deliverables

1. Validated service methods for creating/updating core records.
2. Telegram allowlisted write commands.
3. Local CSV or JSON import support.
4. Optional dashboard forms only if safe and low-cost.
5. Full tests for validation and write flows.

## Security note

API key authentication was intentionally skipped for personal/local use.

Therefore:

- Telegram write commands must remain allowlist-protected.
- Dashboard write forms should either be skipped, local-only, or feature-flagged.
- Do not expose write dashboard routes publicly without auth.
