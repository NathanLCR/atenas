# Atenas — Architecture v0.1

## Guiding Principle

> LLM decides meaning. Code controls structure and actions.

The LLM is never trusted to directly execute anything. All LLM output passes through schema validation, Pydantic validation, and the policy engine before any action is taken.

---

## High-Level Flow

```
User (Telegram / Dashboard)
        │
        ▼
    Atenas API  (FastAPI)
        │
        ▼
  Command Router
        │
        ▼
  Intent Classifier
        │
        ▼
  Skill Registry  ──► Skill Handler
        │
        ▼
  Retrieval Engine
  ├── SQLite metadata
  ├── Markdown/YAML memory files
  ├── Keyword search
  └── Embedding search (Phase 8+)
        │
        ▼
    LLM Router
    ├── Local LLM (Ollama)
    └── Cloud LLM fallback (OpenAI / OpenRouter)
        │
        ▼
  Pydantic Validator
        │
        ▼
  Policy Engine
        │
        ▼
  Action Executor
        │
        ▼
  Storage Layer
  ├── Filesystem (Markdown / YAML — source of truth)
  ├── SQLite (metadata, state, graph, logs)
  └── JSONL logs
```

---

## Component Responsibilities

### API Layer (`app/`)

| File | Responsibility |
|---|---|
| `main.py` | Application entry point, startup/shutdown, lifespan |
| `api.py` | FastAPI routes: /health, /status, API endpoints |
| `bot.py` | Telegram bot handler, allowlist, maps commands to router |
| `dashboard.py` | Jinja2 dashboard routes (Phase 2+) |
| `config.py` | Loads and validates environment config via pydantic-settings |
| `scheduler.py` | APScheduler jobs — stub for Phase 6+ |

### Core Layer (`core/`)

| File | Responsibility |
|---|---|
| `router.py` | Routes parsed commands to the correct skill |
| `skill_registry.py` | Registers skills, indexes commands, resolves handlers |
| `llm_router.py` | Decides local vs cloud; retries; logs calls |
| `memory_manager.py` | Reads/writes Markdown memory files (Phase 4+) |
| `retrieval_engine.py` | Stub for Phase 8 |
| `graph_manager.py` | Stub for Phase 8 |
| `embedding_manager.py` | Stub for Phase 8 |
| `policy_engine.py` | Enforces action rules; blocks forbidden ops |
| `action_executor.py` | Executes validated, approved actions |
| `schemas.py` | All Pydantic models |
| `db.py` | SQLite schema init and connection |
| `utils.py` | Timestamps, slugs, JSONL logging handler |

**Phase 1 note:** `retrieval_engine.py`, `graph_manager.py`, `embedding_manager.py`, and `memory_manager.py` are empty stubs. Do not implement internals until their respective phases.

### Skills Layer (`skills/`)

Each skill is a directory:
```
skills/<name>/
├── __init__.py
├── handler.py     # Command handler logic
├── prompts.py     # LLM prompt templates (when skill uses LLM)
└── schemas.py     # Skill-specific Pydantic models (if any)
```

Tests live in `tests/`, not inside skill directories.

### Storage Layer

```
memory/                  ← human-readable source of truth
├── profile.md
├── preferences.yaml
├── studies/
│   ├── modules.yaml
│   ├── timetable.yaml
│   └── notes/
├── work/
│   ├── shifts.yaml
│   └── workplaces.yaml
├── assignments/
│   ├── active.yaml
│   └── archive/
├── papers/
│   ├── reading_list.yaml
│   └── notes/
├── plans/
│   ├── daily/
│   └── weekly/
└── archive/

data/
└── atenas.sqlite        ← SQLite: metadata, state, graph, logs

logs/
├── events.jsonl
├── llm_calls.jsonl
└── errors.jsonl
```

---

## Storage Responsibility Split

| Data type | Location | Why |
|---|---|---|
| Notes, preferences, shifts, plans | `memory/` Markdown/YAML | Human-readable, editable, inspectable |
| Document metadata | SQLite `documents` table | Fast querying |
| Chunks | SQLite `chunks` table | Fast retrieval |
| Graph nodes/edges | SQLite `nodes`, `edges` tables | Lightweight; no Neo4j in v1 |
| Assignment/task state | SQLite + `memory/assignments/active.yaml` | SQLite for queries; YAML as readable backup |
| LLM call logs | SQLite `llm_calls` table + `logs/llm_calls.jsonl` | Structured analysis |
| Action logs | `logs/events.jsonl` | JSONL for audit trail |

**Rule:** SQLite is never the only copy of user data. The `memory/` files are the source of truth. SQLite can be rebuilt from files if corrupted.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Primary keys | TEXT (UUID strings) | Matches PDF spec; future multi-user safe |
| fatigue_level | TEXT enum (low/medium/high) | Matches PDF spec; simpler than integer 1-5 |
| work_shifts.date | Separate column (YYYY-MM-DD) | Enables easy range queries without datetime parsing |
| Work shift extraction | Array wrapper + needs_confirmation | Supports "I work Mon and Thu" in one message |
| Memory extraction | should_store + domain + importance | LLM can decline noise; structured classification |
| Study plan output | capacity + reason per block + warnings | Auditable decisions; visible constraint violations |
| Confidence threshold | 0.65 everywhere | Single source in config.MIN_CONFIDENCE_THRESHOLD |
| Dashboard | FastAPI + Jinja + HTMX | No JS build step; faster for v1 |

---

## LLM Router Logic

```
Incoming task
    │
    ▼
Is task in local_task_list?
    │
   Yes ──► Call local LLM (Ollama)
    │          │
    │      Validate with Pydantic
    │          │
    │      Pass? ──► Continue
    │          │
    │      Fail? ──► Retry local once
    │                  │
    │              Fail again? ──► Escalate to cloud
    │
   No ──► Call cloud LLM
```

---

## Build Phase Mapping

| Phase | Components built |
|---|---|
| 0 | Specs only |
| 1 | FastAPI skeleton, SQLite init, config, logging, healthcheck, skill registry, policy engine, action executor, status skill, pytest scaffold |
| 2 | Telegram bot, /ping /status /skills via Telegram, basic dashboard |
| 3 | LLM router: Ollama provider, cloud adapter, Pydantic validation, fallback, LLM logging |
| 4 | Memory skill |
| 5 | Work schedule skill |
| 6 | Study planner skill |
| 7 | Assignments skill |
| 8 | Papers, PDF chunking, embeddings, graph |
| 9 | Literature matrix |
