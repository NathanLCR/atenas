# Phase 5 Architecture

## Current architecture

Relevant current components:

```
core/academic/
  planner.py
  service.py
  repository.py
  models.py
  availability.py
core/time.py

app/
  bot.py
  dashboard.py
  templates/

tests/
```

## New files

```
core/academic/
  validators.py         # parsing/validation utilities
  importers.py          # CSV/JSON import logic

app/
  templates/
    data.html           # optional read-only dashboard view

tests/academic/
  test_input_validation.py
  test_importers.py

tests/
  test_data_commands.py
```

## Responsibility split

- **Repository**: insert, update, list, duplicate lookup. No Telegram/CSV parsing.
- **Service**: validation orchestration, create/update workflows, structured results.
- **Importer**: read CSV/JSON, convert to service input, dry-run, report errors, skip duplicates.
- **Telegram**: parse command args, call service, format responses, enforce allowlist.
- **Dashboard**: read-only data pages only. Writes deferred unless feature-flagged.

## Dependency direction

Correct: Telegram/Dashboard/Importer -> AcademicService -> Repository
Incorrect: Repository -> Telegram, Planner -> Telegram, Importer -> Telegram

## Security model

1. Telegram write commands use existing allowlist protection.
2. Dashboard writes disabled by default (ENABLE_DASHBOARD_WRITES=false).
3. No public write surface without auth.
