# Phase 4 — Deterministic Study Planner

## Status

Complete.

## Final checkpoint

Phase 4 completed with:

- `completed_hours` support
- deterministic planner in `core/academic/planner.py`
- planner APIs on `AcademicService`
- Telegram commands:
  - `/plan`
  - `/study`
- dashboard route:
  - `/dashboard/plan`
- computed-on-demand planner
- no planned-block persistence
- no LLM/RAG/agents/external APIs
- all tests passing at checkpoint

## Goal

Turn availability + deadlines into a deterministic study plan.

Atenas should answer:

```text
What should I study today and this week?
```

## Core algorithm

Use:

- open assignments
- due dates
- priorities
- estimated hours
- completed hours
- availability windows

Sort assignments by:

```text
1. due_at ascending
2. priority ascending
3. remaining_minutes descending
4. assignment_id ascending
```

## Planning rules

- include statuses: `todo`, `in_progress`
- exclude: `submitted`, `done`, `cancelled`
- do not schedule after `due_at`
- do not schedule overdue assignments
- split long windows
- default min block: 45 minutes
- default max block: 120 minutes
- default break: 15 minutes
- final short block allowed only if it completes an assignment and is at least 20 minutes
- report unscheduled workload

## Design decision

Plans are computed on demand.

Do not persist planned blocks yet.

Reason:

- avoids stale plans
- simpler invalidation
- deterministic output
- easier tests

## Commands

### `/plan`

Shows weekly plan, grouped by day.

### `/study`

Shows next recommended study block.

## Exit criteria

Phase 4 is complete when Atenas can generate a deterministic weekly plan and next-study recommendation from structured data.
