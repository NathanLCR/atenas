# Atenas Phase 1 — Claude Code Build Prompt

## Context

You are building Phase 1 of **Atenas Core** from scratch.

Atenas is a local-first AI study operating system for working students. Read the full spec docs in `docs/` before writing any code. This prompt summarises the decisions — the docs are the source of truth.

**Phase 1 scope:** A running FastAPI skeleton with SQLite init, config, structured logging, healthcheck, skill registry, policy engine, action executor, status skill, LLM router interface (mock only), Pydantic schemas, and tests. No Telegram bot, no dashboard, no LLM calls, no real features yet.

---

## Reference Documents

Read these before implementing. They contain the corrected schemas, data model, and security rules.

```
docs/PRODUCT_SPEC.md      — what Atenas is
docs/REQUIREMENTS.md      — functional and non-functional requirements
docs/ARCHITECTURE.md      — component map, storage split, build phases
docs/AGENT_POLICY.md      — LLM routing rules, planning rules, safety boundaries
docs/SECURITY.md          — forbidden actions, confirmation rules, prompt injection defence
docs/DATA_MODEL.md        — SQLite schema v1 (corrected), entity definitions, YAML formats
docs/SCHEMAS.md           — all LLM output schemas (corrected), action system
docs/ROADMAP.md           — phase definitions and exit criteria
docs/skills/status.md     — status skill spec (implement this in Phase 1)
```

---

## Critical Design Decisions (already resolved)

These were resolved during spec review. Do not deviate.

| Decision | Value |
|---|---|
| Primary keys | `TEXT` (UUID4 strings) — not INTEGER autoincrement |
| `fatigue_level` | `TEXT` enum: `low`, `medium`, `high` — not INTEGER 1-5 |
| `work_shifts` table | Has a separate `date TEXT` column (YYYY-MM-DD) alongside `start_time`/`end_time` (HH:MM) |
| `WorkShiftsExtracted` schema | Array wrapper: `{"shifts": [...], "needs_confirmation": bool}` — not single object |
| `MemoryItemExtracted` schema | Includes `should_store`, `domain`, `importance`, `summary` — not just content/topic/tags |
| `DailyPlanGenerated` schema | Includes `capacity`, `reason` per block, `warnings` — not just date/blocks |
| Confidence threshold | `0.65` everywhere, from `config.MIN_CONFIDENCE_THRESHOLD` |
| Cost control | `MAX_CLOUD_COST_PER_DAY_USD=1.00`, `MAX_CLOUD_CALLS_PER_DAY=50` in config |
| Dashboard | FastAPI + Jinja + HTMX — no React |
| Graph/embeddings | Empty stubs only in Phase 1 |

---

## Repository Structure to Create

```
atenas-core/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, startup
│   ├── api.py               # /health, /status endpoints
│   ├── config.py            # pydantic-settings config loader
│   ├── bot.py               # Stub — Phase 2
│   ├── dashboard.py         # Stub — Phase 2
│   └── scheduler.py         # Stub — Phase 6
│
├── core/
│   ├── __init__.py
│   ├── db.py                # SQLite schema init + connection helper
│   ├── schemas.py           # All Pydantic models (corrected)
│   ├── skill_registry.py    # Skill registration and command dispatch
│   ├── policy_engine.py     # Forbidden + confirmation-required sets
│   ├── action_executor.py   # Handler registry, policy check before exec
│   ├── llm_router.py        # Interface + mock provider (no real LLM yet)
│   ├── utils.py             # JSONL handler, timestamps, slugify
│   ├── memory_manager.py    # Stub — Phase 4
│   ├── retrieval_engine.py  # Stub — Phase 8
│   ├── graph_manager.py     # Stub — Phase 8
│   └── embedding_manager.py # Stub — Phase 8
│
├── skills/
│   ├── __init__.py
│   └── status/
│       ├── __init__.py
│       └── handler.py       # /ping, /status, /skills handlers
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures (tmp db, settings, etc.)
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_schemas.py
│   ├── test_policy_engine.py
│   ├── test_skill_registry.py
│   ├── test_action_executor.py
│   ├── test_status_skill.py
│   └── test_api.py          # FastAPI TestClient tests for /health, /status
│
├── docs/                    # Already provided — do not modify
├── memory/                  # Empty dirs for runtime
├── data/
├── logs/
├── inbox/
├── output/
├── web/
│   └── templates/           # Empty — Phase 2
│
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## File-by-File Implementation Guide

### `app/config.py`

Use `pydantic-settings`. Load from `.env`. All fields:

```
app_env, app_name
telegram_bot_token (optional), telegram_allowed_user_ids (comma-separated str → list[int])
data_dir, memory_dir, output_dir, inbox_dir, logs_dir (all Path)
local_llm_provider, ollama_base_url, ollama_small_model, ollama_embedding_model
cloud_llm_provider, openai_api_key (optional), openai_model, openrouter_api_key (optional), openrouter_model (optional)
enable_cloud_fallback (bool, default False)
max_cloud_cost_per_day_usd (float, 1.00), max_cloud_calls_per_day (int, 50)
min_confidence_threshold (float, 0.65), max_llm_retries (int, 2)
log_level (str, INFO)
```

Properties: `db_path`, `actions_log_path`, `llm_log_path`, `errors_log_path`.

Singleton via `get_settings()`.

### `core/db.py`

- Use the exact SQL from `docs/DATA_MODEL.md` (the corrected schema with TEXT PKs, date column on work_shifts, CHECK constraints, indexes).
- `init_db(db_path)` → create tables if not exist.
- `get_connection(db_path)` → return configured connection with `foreign_keys=ON`, `row_factory=sqlite3.Row`.
- WAL mode enabled.

### `core/schemas.py`

Implement all Pydantic models matching `docs/SCHEMAS.md` exactly. Key models:

**Enums:** `FatigueLevel(low/medium/high)`, `StudyIntensity(recovery/light/medium/deep)`, `PlanCapacity(low/medium/high)`, `TaskStatus`, `AssignmentStatus`, `Priority`, `MemoryDomain`, `Importance`, `LLMProvider(local/cloud/mock)`, `ActionOutcome`.

**LLM output models (corrected):**
- `WorkShiftItem` + `WorkShiftsExtracted` (array wrapper + needs_confirmation)
- `MemoryItemExtracted` (should_store, domain, importance, summary)
- `StudyBlockGenerated` (with reason field) + `DailyPlanGenerated` (with capacity, warnings)
- `PaperMetadataExtracted`, `LiteratureMatrixEntry`, `FlashcardSetGenerated`

**Storage models:** `WorkShift`, `Assignment`, `Task`, `MemoryItem`, `LLMCallRecord`

**Action system:** `ActionProposal`, `ActionResult`

All IDs default to `uuid4()`. All timestamps default to `utc_now()`.

### `core/policy_engine.py`

- `FORBIDDEN_ACTIONS: frozenset[str]` — the exact set from `docs/SECURITY.md`.
- `CONFIRMATION_REQUIRED: frozenset[str]` — the exact set.
- `PolicyDecision` dataclass: `allowed`, `outcome`, `reason`.
- `PolicyEngine.check(proposal) → PolicyDecision`. Stateless.
- Forbidden → always blocked. Confirmation-required → blocked unless `requires_confirmation=True`.
- Log every decision.

### `core/action_executor.py`

- `register_action(action_type, handler)` — called at startup by skills.
- `execute(proposal) → ActionResult` — policy check first, then handler lookup, then call.
- Catch all exceptions in handler execution.
- Log every execution.

### `core/skill_registry.py`

- `SkillInfo` dataclass: `name`, `description`, `commands`, `enabled`, `handler`.
- `SkillRegistry`: register, get by name, get by command, list all, list enabled.
- Command index: `dict[str, str]` mapping command → skill name.
- Singleton via `get_registry()`.
- Handler signature: `async def handler(command: str, args: str, user_id: int) -> str`

### `core/llm_router.py`

Phase 1: interface and mock provider only. No Ollama, no cloud.

- `LLMResponse` dataclass: `text`, `parsed` (dict | None), `provider`, `model`, `input_tokens`, `output_tokens`, `latency_ms`.
- `LLMRouter` class with `call(task_type, prompt, schema_model) → LLMResponse`.
- Phase 1 implementation: always returns a mock response.
- Log every call to `logs/llm_calls.jsonl` even in mock mode.

### `core/utils.py`

- `utc_now() → str` (ISO 8601 UTC).
- `slugify(text) → str`.
- `JSONLHandler(filepath)` — logging handler that writes structured JSONL.
- `setup_logging(logs_dir, level)` — configure root logger with console + JSONL.

### `core/memory_manager.py`, `core/retrieval_engine.py`, `core/graph_manager.py`, `core/embedding_manager.py`

Empty stubs. Single docstring explaining what phase they belong to. No implementation.

```python
"""
core/memory_manager.py — Memory file management. Phase 4.
"""
```

### `skills/status/handler.py`

Implement the status skill per `docs/skills/status.md`:

- `handle_ping() → str` — returns "🏓 pong"
- `handle_status(db_path) → str` — reads SQLite counts (assignments, upcoming deadlines, this week's shifts). Handles empty DB gracefully.
- `handle_skills(registry) → str` — lists all registered skills with status icons.
- Register as a skill with commands: `/ping`, `/status`, `/skills`.

### `app/main.py`

- Create FastAPI app with lifespan.
- On startup: setup logging, init DB, register skills, include API router.
- On shutdown: log clean shutdown.

### `app/api.py`

- `GET /health` → `{"status": "ok"}`.
- `GET /status` → calls status skill handler, returns response.
- `GET /skills` → calls skills handler, returns response.

### `app/bot.py`, `app/dashboard.py`, `app/scheduler.py`

Stubs. Single docstring.

---

## Tests to Write

### `tests/conftest.py`
- `tmp_db` fixture: creates a temporary SQLite DB with schema.
- `settings` fixture: returns Settings with temp directories.
- `registry` fixture: returns a fresh SkillRegistry.

### `tests/test_config.py`
- Default settings load without .env.
- db_path property resolves correctly.

### `tests/test_db.py`
- `init_db` creates all tables.
- `init_db` is idempotent (safe to call twice).
- `get_connection` returns a connection with `row_factory=Row`.

### `tests/test_schemas.py`
- `WorkShiftsExtracted` validates correct input.
- `WorkShiftsExtracted` rejects missing `shifts` field.
- `MemoryItemExtracted` validates with `should_store=false`.
- `DailyPlanGenerated` validates with `capacity`, `warnings`, `reason`.
- `ActionProposal` validates correctly.
- `FatigueLevel` rejects invalid values.

### `tests/test_policy_engine.py`
- Forbidden action (`shell_exec`) → blocked.
- Confirmation-required action without confirmation → blocked with `NEEDS_CONFIRMATION`.
- Confirmation-required action with `requires_confirmation=True` → allowed.
- Allowed action (`write_memory`) → passes.
- Every item in `FORBIDDEN_ACTIONS` is tested.

### `tests/test_skill_registry.py`
- Register a skill → find it by name.
- Find skill by command.
- Unknown command returns None.
- Disabled skill not returned by `get_by_command`.

### `tests/test_action_executor.py`
- Execute forbidden action → blocked.
- Execute with registered handler → success.
- Execute with no handler → error.
- Handler that raises exception → caught, returns error.

### `tests/test_status_skill.py`
- `handle_ping` returns "🏓 pong".
- `handle_status` with empty DB → shows zeros.
- `handle_skills` with registered skills → lists them.

### `tests/test_api.py`
- `GET /health` → 200, `{"status": "ok"}`.
- `GET /status` → 200, contains "Atenas".
- `GET /skills` → 200, contains "status".

---

## Configuration Files

### `.env.example`
```
APP_ENV=development
APP_NAME=Atenas
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=
LOCAL_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_SMALL_MODEL=llama3.2
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
CLOUD_LLM_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
ENABLE_CLOUD_FALLBACK=false
MAX_CLOUD_COST_PER_DAY_USD=1.00
MAX_CLOUD_CALLS_PER_DAY=50
MIN_CONFIDENCE_THRESHOLD=0.65
MAX_LLM_RETRIES=2
LOG_LEVEL=INFO
```

### `requirements.txt`
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.8.2
pydantic-settings==2.4.0
python-telegram-bot==21.6
httpx==0.27.2
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
```

### `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data logs memory inbox output
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `docker-compose.yml`
```yaml
services:
  atenas:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./memory:/app/memory
      - ./inbox:/app/inbox
      - ./output:/app/output
    env_file:
      - .env
    restart: unless-stopped
```

### `.gitignore`
```
.env
__pycache__/
*.pyc
data/
logs/
inbox/
output/
.pytest_cache/
*.egg-info/
dist/
build/
```

### `pyproject.toml`
```toml
[project]
name = "atenas-core"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Acceptance Criteria

Phase 1 is done when ALL of the following are true:

1. `docker-compose up` starts the API without errors.
2. `GET /health` returns `{"status": "ok"}`.
3. `GET /status` returns a formatted status string with zero counts.
4. `GET /skills` lists the status skill as registered.
5. SQLite database is created at `data/atenas.sqlite` with all tables.
6. Logs are written to `logs/events.jsonl`.
7. Policy engine blocks every action in `FORBIDDEN_ACTIONS`.
8. Policy engine requires confirmation for every action in `CONFIRMATION_REQUIRED`.
9. Action executor catches handler exceptions without crashing.
10. All Pydantic schemas validate correct input and reject invalid input.
11. `pytest` passes all tests with zero failures.
12. No `graph_manager.py`, `embedding_manager.py`, `retrieval_engine.py`, or `memory_manager.py` internals are implemented — stubs only.

---

## Rules

1. Do not implement anything outside Phase 1 scope.
2. Do not modify files in `docs/`.
3. Do not add dependencies beyond `requirements.txt`.
4. Use the exact SQLite schema from `docs/DATA_MODEL.md`.
5. Use the exact Pydantic schemas from `docs/SCHEMAS.md`.
6. Use the exact policy sets from `docs/SECURITY.md`.
7. All files must have a module docstring explaining their purpose.
8. All tests must pass with `pytest` and no external dependencies (no Ollama, no API keys).
9. Every function that writes to disk or DB must log the operation.
10. Every test file must be independently runnable.
