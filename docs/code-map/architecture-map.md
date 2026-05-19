# Architecture Map

## System overview

Atenas is a local-running, Telegram-first study assistant for working students.
It combines deterministic scheduling, Telegram bot interaction, an LLM agent
with controlled tools, notes/files retrieval, and a read-only local dashboard.

## Core layers

```text
Telegram Bot (python-telegram-bot)
        ↓
    Allowlist check
        ↓
    Slash commands OR LLM tool agent
        ↓
    Tool registry / command handlers
        ↓
    Services (core/academic/service.py, core/knowledge/service.py, core/retrieval/service.py)
        ↓
    Repositories (core/academic/repository.py, core/knowledge/repository.py)
        ↓
    SQLite (core/db.py, retrieval_chunks)

FastAPI Dashboard (app/dashboard.py)
        ↓
    Services (same as above)
        ↓
    Jinja Templates (app/templates/)
```

## Key design principles

1. **Deterministic** — no randomness in scheduling/planning.
2. **Local-running** — SQLite/files/dashboard/API stay local.
3. **Telegram first** — Telegram is the main product surface.
4. **Tool-mediated LLM** — the LLM calls schemas, not services directly.
5. **Soft archive** — notes/files use `archived=1` instead of hard delete.
6. **Source-grounded retrieval** — RAG answers are generated only after sources are found; otherwise they return the no-source fallback.
7. **Policy-checked writes** — LLM-initiated writes require confirmation and policy.

## Data flow

```text
User → Telegram command → parse_kv_args → Service validation → Repository SQL → Response
User → Telegram plain text → LLM agent → Tool registry → Service validation → Repository SQL → Response
User → Dashboard URL → Service query → Jinja template → HTML
User → /ask_notes or /dashboard/retrieval → RetrievalService → retrieval_chunks → Ollama answer with sources
```

## Important boundaries

- Services handle validation and business logic.
- Repositories handle only SQL CRUD.
- Telegram handlers authenticate, parse commands, orchestrate tools, and format responses.
- Dashboard routes render local read-only templates; no write forms.
- Retrieval indexes only registered, non-archived notes and supported text files.
- No web search, OCR/PDF parsing, automatic filesystem ingestion, or external LLM fallback by default.
- `app/` may import `core/`; `core/` must not import `app/`.
- Settings are injected into services rather than hidden behind `app.config` imports.

## Related docs

- `core-academic.md` — scheduling engine
- `core-knowledge.md` — notes/files/search/retrieval
- `telegram.md` — command handlers
- `dashboard.md` — web routes
- `database-schema.md` — SQLite schema
