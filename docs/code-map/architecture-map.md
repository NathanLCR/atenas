# Architecture Map

## System overview

Atenas is a local-first study operating system for working students. It combines deterministic scheduling, Telegram bot interaction, and a read-only web dashboard.

## Core layers

```text
Telegram Bot (python-telegram-bot)
        ↓
    Commands (app/bot.py)
        ↓
    Services (core/academic/service.py, core/knowledge/service.py)
        ↓
    Repositories (core/academic/repository.py, core/knowledge/repository.py)
        ↓
    SQLite (core/db.py)

FastAPI Dashboard (app/dashboard.py)
        ↓
    Services (same as above)
        ↓
    Jinja Templates (app/templates/)
```

## Key design principles

1. **Deterministic** — no randomness in scheduling/planning.
2. **Local-first** — SQLite only, no cloud sync.
3. **Telegram write, dashboard read** — write commands via allowlisted Telegram; dashboard is read-only.
4. **No LLM by default** — LLM routing exists but is not used in core scheduling.
5. **Soft archive** — notes/files use `archived=1` instead of hard delete.

## Data flow

```text
User → Telegram command → parse_kv_args → Service validation → Repository SQL → Response
User → Dashboard URL → Service query → Jinja template → HTML
```

## Important boundaries

- Services handle validation and business logic.
- Repositories handle only SQL CRUD.
- Telegram handlers parse messages and format responses.
- Dashboard routes render templates; no write forms.

## Related docs

- `core-academic.md` — scheduling engine
- `core-knowledge.md` — notes/files/search
- `telegram.md` — command handlers
- `dashboard.md` — web routes
- `database-schema.md` — SQLite schema
