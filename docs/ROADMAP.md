# Atenas — Roadmap v0.1

## Phase 0 — Specs ✅

All architectural decisions documented. Conflicts between PDF spec and generated specs resolved.

---

## Phase 1 — Foundation Skeleton

**Goal:** A running application with no LLM, no Telegram, no real features — but correct structure.

**Deliverables:**
- FastAPI app boots cleanly
- SQLite schema initialises on startup
- Config loads from `.env` with validation
- Structured JSONL logging works
- `/health` endpoint returns 200
- Skill registry loads and lists skills
- Policy engine blocks all forbidden actions
- Action executor logs but defers to registered handlers
- Status skill handles /ping, /status, /skills as API endpoints
- LLM router interface with mock provider (no real LLM yet)
- Pydantic schemas for all core entities
- pytest scaffold with tests for: policy engine, skill registry, schema validation, DB init, healthcheck
- .env.example, Dockerfile, docker-compose.yml, requirements.txt

**Exit criteria:** `docker-compose up` starts cleanly; healthcheck passes; all tests pass.

---

## Phase 2 — Telegram Bot + Basic Dashboard

**Deliverables:** Telegram bot, /ping /status /skills via Telegram, allowlist enforcement, basic Jinja dashboard.

---

## Phase 3 — LLM Router

**Deliverables:** Ollama provider, cloud adapter, Pydantic validation, retry → fallback, LLM call logging.

---

## Phase 4 — Memory Skill

**Deliverables:** /memory add, /memory search, /memory show, Markdown writer, SQLite memory_items.

---

## Phase 5 — Work Schedule Skill

**Deliverables:** /work add, /work week, /work clear, shift extraction, fatigue rules.

---

## Phase 6 — Study Planner Skill

**Deliverables:** /study today, /study week, availability block computation, fatigue-aware planning.

---

## Phase 7 — Assignments Skill

**Deliverables:** /assignment add, /assignment list, /assignment plan, deadline risk scoring.

---

## Phase 8 — Papers and Embeddings

**Deliverables:** PDF upload, metadata extraction, chunking, embedding search.

---

## Phase 9 — Literature Matrix

**Deliverables:** /matrix update, /matrix export, CSV/Markdown output.
