# Phase 3 — Academic + Work Scheduling Foundation

## Status

Complete.

## Final checkpoint

Phase 3 completed with:

- deterministic academic scheduling package under `core/academic`
- `core/time.py`
- configurable timezone defaulting to `Europe/Dublin`
- expanded SQLite schema/migrations
- timezone-aware UTC timestamps
- no hardcoded personal status output
- dashboard pages:
  - `/dashboard/week`
  - `/dashboard/deadlines`
- Telegram commands:
  - `/today`
  - `/week`
  - `/deadlines`
  - `/availability`
- tests passing at checkpoint

## Goal

Make Atenas understand structured student/work life data.

The system should answer:

```text
What do I have today, what do I have this week, what deadlines are coming, and how much realistic study time do I have?
```

## Data entities

- study modules
- class sessions
- work shifts
- assignments/deadlines

## Availability algorithm

For each day:

1. Create daily boundary, default `08:00–22:00`.
2. Add class blocks.
3. Add work shifts.
4. Merge overlapping blocked intervals.
5. Calculate free study windows.
6. Filter windows below minimum duration.
7. Trim past time for today.
8. Return daily and weekly totals.

## Constraints

- deterministic only
- no LLM
- no natural-language parsing
- no calendar sync
- no external API
- no personal data hardcoded

## Tests

Required tests:

- schema/repository tests
- class/work/assignment tests
- overlapping interval tests
- availability tests
- Telegram command tests
- dashboard tests

## Exit criteria

Phase 3 is complete when Atenas can compute today/week availability from structured academic and work data.
