# Core Academic — Scheduling & Planning

## Purpose

Deterministic scheduling engine for modules, classes, work shifts, assignments, availability calculation, and study planning.

## Files

| File | Role |
|------|------|
| `core/academic/models.py` | Pydantic models for all domain entities |
| `core/academic/repository.py` | SQLite CRUD for academic tables |
| `core/academic/service.py` | Business logic, validation, availability, planning |
| `core/academic/validators.py` | Input parsing (kv args, datetime, status, priority) |
| `core/academic/planner.py` | Study plan generation algorithm |
| `core/academic/availability.py` | Free time calculation |

## Main classes

- `AcademicService` — primary entry point for scheduling operations.
- `AcademicRepository` — SQLite persistence layer.
- `StudyModule`, `ClassSession`, `WorkShift`, `Assignment` — Pydantic models.
- `StudyPlan`, `PlannedStudyBlock` — planning output models.

## Data flow

```text
Command → parse_kv_args → AcademicService.add_*() → validate → AcademicRepository.create_*() → CommandResult
Query → AcademicService.list_*() → AcademicRepository.list_*() → Pydantic models
```

## Important constraints

- IDs are UUID4 strings (TEXT in SQLite), not integers.
- Datetimes are stored as ISO strings in local timezone (Europe/Dublin).
- Class sessions use weekday integers (0=Mon, 6=Sun).
- Assignment statuses: `todo`, `in_progress`, `submitted`, `done`, `cancelled`.
- Priority is 1-5 (1=critical, 5=low).

## Pitfalls

- Do not change ID generation from UUID4 to integers without migrating all academic tables.
- `parse_kv_args` uses regex; quoted values with spaces require double quotes.
- Availability calculation assumes a fixed day window (default 07:00–23:00).
- Study planner requires `estimated_hours` on assignments to generate blocks.

## Related tests

- `tests/academic/test_repository.py`
- `tests/academic/test_schedule_service.py`
- `tests/academic/test_availability.py`
- `tests/academic/test_planner.py`
- `tests/academic/test_input_validation.py`
- `tests/test_schedule_commands.py`
- `tests/test_planning_commands.py`
