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
| 8 | Complete | Controlled retrieval/RAG foundation |
| 9 | Complete | Notifications + reminders |

Current verified test baseline:

```text
383 passed
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

## Backlog / Known Gaps

Not blocking Phase 8. Logged so they are not rediscovered later.

### BL-01 — Recurring work shifts

**Problem.** `work_shifts` stores concrete dated rows with strict `start_at` /
`end_at` datetimes and has no recurrence concept. `class_sessions` — specified
in the same Phase 3 — *is* weekly-recurring (`weekday` + `start_time` /
`end_time`). Work and class scheduling are therefore asymmetric for no
principled reason.

**Impact.** Real usage is fixed weekly shift patterns (e.g. Tue/Sat/Sun, plus
alternating Fridays). Without recurrence, every week of shifts must be
hand-entered or bulk-imported as discrete rows. This directly weakens the
planner: the Phase 4 capacity rule ("a heavy week ≥ 4 shifts cuts planned
study minutes ≥ 30%") only fires if shifts are actually present, so an empty
or stale `work_shifts` table silently produces over-optimistic plans.

**Related gap.** Biweekly recurrence (alternating-Friday classes/shifts) is
unmodeled even for `class_sessions`, which is weekly-only.

**Suggested direction.** Mirror the `class_sessions` recurring model for work:
a recurring-shift rule (weekday + start/end + effective date range, optional
interval for biweekly) that deterministically expands into concrete
`work_shifts` rows. Expansion must stay deterministic per the spec-driven
constraint. This is net-new capability — give it its own spec, do not hack it
into `importers.py`.

**Touch points.** `core/db.py` (`work_shifts` schema),
`core/academic/{models,validators,service,repository,importers}.py`, the
`/work` command surface, and `docs/phases/phase-03-academic-work-scheduling.md`.

**Priority.** Enhancement / post-MVP or a Phase 3 follow-up. Does not block
the Phase 8 RAG work.
