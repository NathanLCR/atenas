# Atenas — Roadmap

## Status

This file is historical. It is useful for understanding the original phase
sequence, but the current operating direction lives in:

- `docs/HANDOFF.md`
- `docs/HANDOFF_NL_INTERFACE.md`
- `docs/phases/phase-natural-language-interface.md`
- `docs/phases/README.md`

Current product posture as of 2026-05-19:

- Local-running app.
- Telegram-first interface.
- LLM agent with controlled Atenas tools.
- Slash commands preserved as shortcuts.
- Local dashboard/API only.

Do not rely on old test counts in this file. Run `pytest` in the current
workspace.

---

## Phase 0 — Specs ✅

All architectural decisions documented. Conflicts between PDF spec and generated specs resolved.

---

## Phase 1 — Foundation Skeleton ✅

Implemented. FastAPI app, SQLite init, config, JSONL logging, skill registry,
policy engine, action executor, mock LLM router, and the deterministic status
skill are in place with passing tests.

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

## Dependency ordering (why the phases are in this order)

The study planner is the product's core value, but it is a *consumer*: it
cannot produce a correct plan until its hard inputs exist. Its inputs are
work shifts (Phase 5), the class timetable (Phase 6), and assignments +
deadlines (Phase 7). Therefore the planner is Phase 8 — **after** every input
it depends on. Building it earlier would force it to violate its own policy
(AGENT_POLICY: "always query assignments and the work schedule before
planning") for lack of data to query.

---

## Phase 4 — Memory Skill

**Deliverables:** /memory add, /memory search, /memory show, Markdown writer, SQLite memory_items, `sensitive` classification honoured by the cloud gate.

---

## Phase 5 — Work Schedule Skill

**Deliverables:** /work add, /work week, /work clear, shift extraction, fatigue rules.

---

## Phase 6 — Class Timetable Skill

**Deliverables:** /timetable add, /timetable week, /timetable clear, recurring class-session ingestion, YAML `timetable.yaml` + SQLite `class_sessions`. Class sessions become hard scheduling blocks equivalent to work shifts. (Implements FR-05 — previously had no phase.)

---

## Phase 7 — Assignments Skill

**Deliverables:** /assignment add, /assignment list, /assignment plan, /assignment risk, deadline-risk scoring (formula in AGENT_POLICY), assignment + task estimates.

---

## Phase 8 — Study Planner Skill

Built only after work shifts, class timetable, and assignments exist.

**Deliverables:** /study today, /study week, deterministic availability-block computation, code-authored slots + intensity caps, LLM slot-assignment only (no LLM-authored times), plan persistence.

**Exit criteria (falsifiable — see PLAN QUALITY below):** the generated plan must pass every invariant in the plan-quality rubric, automatically, on a seeded fixture week.

---

## Phase 9 — Papers + PDF Ingestion

**Deliverables:** PDF upload, type/size validation, metadata extraction, deterministic chunking, `documents` + `chunks` populated. No embeddings yet.

---

## Phase 10 — Embeddings + Semantic Search

**Deliverables:** embedding generation (Ollama `nomic-embed-text`), embedding storage per the DATA_MODEL semantic-search design, brute-force cosine retrieval, `/papers search` semantic mode.

---

## Phase 11 — Literature Matrix

**Deliverables:** /matrix update, /matrix export, CSV/Markdown output.

---

## Phase 12 — Flashcards

**Deliverables:** /flashcards make <topic>, `FlashcardSetGenerated`. (Implements FR-10 — previously had no phase.)

---

## Deferred to post-v1 — Knowledge Graph

The `nodes`/`edges` tables and the graph ontology remain in the schema as
reserved structure, but **no v1 phase builds or consumes the graph**. It had
no defined query or consumer, so it is explicitly out of v1 scope to avoid
speculative complexity. Revisit only when a concrete question requires it
that the relational tables + retrieval cannot answer.

---

## PLAN QUALITY — falsifiable acceptance for the planner (Phase 8)

"Realistic plan" is otherwise unfalsifiable. A plan is **accepted** only if an
automated check confirms ALL of the following on a seeded fixture week:

1. **No hard-block collision.** No study slot overlaps any work shift or class session.
2. **Availability bound.** Total scheduled study minutes ≤ computed available minutes that day.
3. **Fatigue caps respected.** No block exceeds its slot's `max_intensity`; no `deep` block before 10:00 the morning after a shift ending ≥ 23:00; a `high`-fatigue day has only `recovery`/`light`.
4. **Deadline coverage.** Every assignment with a deadline ≤ 72h and priority ≥ high receives ≥ 1 block before its deadline (or an explicit warning explaining why it cannot).
5. **Slot integrity.** Every `BlockAssignment.slot_id` references a real code-authored slot; no times are LLM-authored.
6. **Determinism.** Same inputs → same plan (LLM temperature pinned; ties broken by a fixed rule), so the suite is reproducible.
7. **Capacity honesty.** A heavy week (≥ 4 shifts) reduces total planned study minutes by ≥ 30% vs. an otherwise-identical light week.

Any violation = plan rejected. These are the Phase 8 exit criteria.
