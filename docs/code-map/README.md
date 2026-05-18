# Atenas Code Map

Lightweight architecture documentation for coding agents and humans.

## Structure

```text
docs/code-map/
  README.md            ← you are here
  architecture-map.md  ← system overview and data flow
  core-academic.md     ← scheduling, planning, availability
  core-knowledge.md    ← notes, files, search (Phase 6)
  telegram.md          ← bot commands and handlers
  dashboard.md         ← FastAPI routes and templates
  database-schema.md   ← SQLite tables and relationships
```

## Quick start

- **New feature?** Read `architecture-map.md` first.
- **Telegram command?** Read `telegram.md`.
- **Dashboard page?** Read `dashboard.md`.
- **Data model change?** Read `database-schema.md`.
- **Scheduling logic?** Read `core-academic.md`.
- **Notes/files/search?** Read `core-knowledge.md`.

## Rules

- Docstrings only for non-obvious public functions.
- Comments only for tricky logic.
- Tests show expected behaviour.
- Do not change runtime behaviour when updating docs.

## Testing

```bash
python3 -m pytest
```
