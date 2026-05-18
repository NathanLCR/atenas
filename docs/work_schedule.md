# Skill Spec — Work Schedule

## Purpose
Accept and store work shift entries. Make them available to the planner as hard scheduling constraints. Work schedule is first-class — planner must never generate a plan without reading it.

## Commands

| Command | Description |
|---|---|
| `/work add <text>` | Parse and store shift(s) from natural language |
| `/work week` | Show shifts for current week |
| `/work clear` | Clear shifts (requires confirmation) |

## LLM Usage
- `/work add`: local LLM extracts fields. Schema: `WorkShiftsExtracted` (array + needs_confirmation). Uses the `add_work_shift` allowlisted action.
- `/work clear` is in `CONFIRMATION_REQUIRED` — blocked unless `user_confirmed`.
- Fatigue level is TEXT enum: `low`, `medium`, `high`.
- `start_time`/`end_time` are wall-clock `HH:MM` in `settings.timezone`; `created_at`/`updated_at` are UTC ISO 8601.
- `needs_confirmation=true`, or low self-reported `confidence` corroborated by a thin result → ask the user before storing (confidence is a secondary signal only).

## Storage
- Write: `memory/work/shifts.yaml` + SQLite `work_shifts`
- Read: SQLite `work_shifts` for queries

## Phase
Phase 5. Not implemented in Phase 1.
