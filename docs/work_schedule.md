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
- `/work add`: local LLM extracts fields. Schema: `WorkShiftsExtracted` (array + needs_confirmation).
- Fatigue level is TEXT enum: `low`, `medium`, `high`.
- `confidence < 0.65` or `needs_confirmation=true` → ask user before storing.

## Storage
- Write: `memory/work/shifts.yaml` + SQLite `work_shifts`
- Read: SQLite `work_shifts` for queries

## Phase
Phase 5. Not implemented in Phase 1.
