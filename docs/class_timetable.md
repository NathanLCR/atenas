# Skill Spec — Class Timetable

## Purpose
Accept and store a recurring class timetable. Class sessions are hard
scheduling constraints, exactly equivalent to work shifts: the planner must
never schedule study over a class session. Implements FR-05.

## Commands

| Command | Description |
|---|---|
| `/timetable add <text>` | Parse and store class session(s) from natural language |
| `/timetable week` | Show class sessions for the current week |
| `/timetable clear` | Clear the timetable (requires confirmation) |

## LLM Usage
- `/timetable add`: local LLM extracts fields. Schema: `ClassSessionsExtracted` (array + `needs_confirmation`), mirroring `WorkShiftsExtracted`.
- `confidence < MIN_CONFIDENCE_THRESHOLD` or `needs_confirmation=true` → ask the user before storing.

## Storage
- Write: `memory/studies/timetable.yaml` + SQLite `class_sessions`
- Read: SQLite `class_sessions` for queries
- Recurrence is stored on the session (`recurrence` column, e.g. `weekly`); the planner expands recurrence into concrete dated blocks at plan time.

## Time & timezone
- `start_time`/`end_time` are wall-clock `HH:MM` interpreted in `settings.timezone`.
- `created_at`/`updated_at` are UTC ISO 8601.

## Safety Rules
1. `/timetable clear` is in `CONFIRMATION_REQUIRED` — never clear without explicit confirmation.
2. Class sessions are treated as immovable hard blocks by the planner.
3. Add actions use the `add_class_session` allowlisted action type.

## Phase
Phase 6. Not implemented in Phase 1.
