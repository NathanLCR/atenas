# Phase 5 Requirements

## Scope

Phase 5 adds controlled input/editing for data already used by the planner.

## In scope

### FR-01 — Add study module

Required: `name`
Optional: `code`, `lecturer`, `notes`

### FR-02 — Add class session

Required: `title`, `weekday`, `start_time`, `end_time`
Optional: `module_id`, `location`, `notes`

Rules: weekday 0-6, start_time < end_time, weekly only, active defaults true.

### FR-03 — Add work shift

Required: `title`, `start_at`, `end_at`
Optional: `location`, `role`, `energy_cost`, `notes`

Rules: start_at < end_at, energy_cost 1-5.

### FR-04 — Add assignment

Required: `title`, `due_at`
Optional: `module_id`, `priority`, `status`, `weight`, `estimated_hours`, `completed_hours`, `notes`

Defaults: status=todo, priority=3, completed_hours=0.

### FR-05 — Update assignment status

Allowed: todo, in_progress, submitted, done, cancelled.

### FR-06 — Update completed hours

Rules: cannot be negative, may exceed estimated_hours (planner treats remaining as 0).

### FR-07 — List data for verification

Minimum Telegram commands: `/modules`, `/classes`, `/shifts`, `/assignments`.

### FR-08 — Import fixture files

Required: CSV for assignments, CSV for work shifts.
Preferred: CSV for modules, CSV for class sessions, JSON bundle.
Avoid YAML unless PyYAML already exists.

### FR-09 — Dry-run import

Parse, validate, report errors and would-be-created records, no DB changes.

### FR-10 — Idempotent-ish imports

Skip duplicates by default, report skipped rows.

## Out of scope

LLM parsing, natural-language input, Google Calendar sync, notification scheduling,
recurring work shifts, complex recurrence, multi-user profiles, public dashboard writes,
PDF ingestion, RAG, embeddings, agent behaviour.
