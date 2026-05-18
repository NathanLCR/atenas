# Atenas — Requirements v0.1

## Functional Requirements

### FR-01 — Telegram Interface
- System MUST accept commands via Telegram bot.
- System MUST respond with structured, readable output.
- System MUST reject unrecognised commands with a helpful message.
- System MUST NOT execute dangerous actions without confirmation.

### FR-02 — Web Dashboard
- System MUST expose a read-only web dashboard at minimum.
- Dashboard MUST show: tasks, assignments, work schedule, daily plan, papers, memory, logs.
- Dashboard SHOULD allow basic editing of assignments and work shifts.
- Dashboard MUST NOT expose raw database or filesystem paths to the browser.

### FR-03 — Memory
- System MUST allow storing free-text memory items via `/memory add`.
- System MUST allow searching memory via `/memory search <query>`.
- Memory MUST be persisted to human-readable Markdown files.
- Memory MUST also be indexed in SQLite for fast retrieval.
- Memory items MUST have: content, summary, domain, topic, tags, importance, `sensitive`, source, created_at, updated_at.
- LLM extraction schema MUST include `should_store` boolean so the model can decline to store noise.
- LLM extraction schema MUST include `sensitive` boolean. Items marked
  `sensitive` MUST NOT be sent to a cloud LLM (as content or retrieved
  context) without explicit per-use user confirmation.

### FR-04 — Work Schedule
- System MUST accept work shift entries: date, start_time, end_time, workplace, fatigue_level.
- Fatigue level MUST be a TEXT enum: `low`, `medium`, `high`.
- LLM extraction MUST support multiple shifts from one message (array wrapper).
- LLM extraction MUST include `needs_confirmation` boolean for ambiguous input.
- System MUST store shifts and expose them for planning.
- System MUST treat shifts as hard blocks in the planner.
- System MUST apply fatigue rules to adjacent study blocks.
- System MUST support `/work add`, `/work week`, `/work clear`.

### FR-05 — Class Timetable
- System MUST accept a recurring class timetable.
- Class sessions MUST be treated as hard blocks equivalent to work shifts.
- Timetable MUST be storable as YAML and queryable from SQLite.

### FR-06 — Assignments and Deadlines
- System MUST accept assignment entries with: title, module, deadline, estimated_hours, priority.
- System MUST track tasks within assignments.
- System MUST calculate deadline risk score.
- System MUST support `/assignment add`, `/assignment list`, `/assignment plan`, `/assignment risk`.

### FR-07 — Study Planner
- System MUST generate a daily study plan given: available blocks, assignments, fatigue state.
- System MUST generate a weekly study plan.
- Plans MUST respect work shift blocks and class session blocks.
- Plans MUST apply fatigue rules (see AGENT_POLICY.md / study_planner.md).
- Plans MUST include `capacity` (low/medium/high), `reason` per block, and `warnings` array.
- All block times MUST be authored by deterministic code. The LLM MUST only
  assign prioritised tasks to code-computed slots (`slot_id`) and MUST NOT
  emit or modify any time. Code MUST reject any assignment referencing an
  unknown slot or exceeding the slot's intensity cap.
- The planner MUST pass every invariant in the ROADMAP "PLAN QUALITY" rubric
  automatically on a seeded fixture week; that suite is its definition of done.
- Plans MUST be saved to `memory/plans/daily/` and `memory/plans/weekly/`.

### FR-08 — PDF and Paper Ingestion
- System MUST accept PDF uploads via Telegram or dashboard.
- System MUST extract and store: title, authors, year, abstract, keywords, file path.
- System MUST chunk PDFs into overlapping text segments.
- System MUST embed chunks and store embeddings for retrieval.
- System MUST support `/papers add`, `/papers list`, `/papers search`, `/papers summarize`.

### FR-09 — Literature Matrix
- System MUST extract structured fields from papers: research question, methodology, findings, limitations.
- System MUST aggregate extracted fields into a matrix (CSV or Markdown table).
- System MUST support `/matrix update`, `/matrix export`.

### FR-10 — Flashcards
- System MUST generate simple Q&A flashcards from notes or paper summaries.
- System MUST support `/flashcards make <topic>`.

### FR-11 — LLM Routing
- System MUST route routine tasks to local LLM (Ollama).
- System MUST escalate to cloud LLM when: local output fails schema validation twice, task is complex, user requests high quality.
- Primary escalation signals MUST be reliable ones: schema-validation
  failure, explicit cloud task class, explicit user quality request,
  >6 conflicting constraints.
- Self-reported `confidence` is a SECONDARY hint only (uncalibrated, model-
  authored). `MIN_CONFIDENCE_THRESHOLD` (0.65) MUST NOT be the sole basis
  for any safety or correctness decision.
- System MUST define terminal-failure behaviour: after the attempt cap
  (≤ 3 total), it MUST NOT act on unvalidated output, MUST tell the user
  nothing was saved, and MUST log the failure (no silent loss).
- System MUST log every LLM call: model, prompt_tokens, response_tokens, latency, provider, task_type, estimated_cost.

### FR-12 — Logging
- System MUST write structured JSONL logs for: every command, every LLM call, every action, every policy decision.
- Logs MUST include: timestamp, event_type, source, payload_summary, outcome.
- Logs MUST be stored in `logs/`.

### FR-13 — Safety and Policy
- System MUST validate all LLM output against Pydantic schema before acting.
- System MUST pass validated output through the policy engine.
- System MUST block forbidden actions unconditionally.
- System MUST require confirmation for destructive actions.

---

## Non-Functional Requirements

### NFR-01 — Local-First
- Core functionality MUST work without internet access.
- Cloud LLM is optional and must degrade gracefully if unavailable.

### NFR-02 — Performance (budgeted against the actual pipeline)

The old flat "10 s for simple queries" ignored that an LLM path is
local-attempt → validate → maybe-retry → maybe-escalate → cloud round-trip
on commodity hardware. Budgets are per path:

- **Deterministic commands** (`/ping`, `/status`, `/skills`, `/work week`,
  `/timetable week`, listing, reading): MUST complete < 2 s.
- **Single local-LLM commands** (memory add, shift/class extraction):
  TARGET < 12 s; HARD timeout 20 s. On timeout: abort cleanly, tell the
  user, save nothing (NFR-03), no partial write.
- **Escalating / cloud commands** (weekly plan, synthesis): MAY take up to
  45 s. The user MUST get an immediate "working…" acknowledgement so the
  channel never appears hung.
- **PDF ingestion**: MAY take up to 2 min/document; runs async with progress,
  never blocking the command channel.
- Every LLM path MUST have an enforced timeout and a deterministic or
  cached fallback (NFR-01) so a slow/absent model degrades, not hangs.

### NFR-03 — Reliability
- System MUST NOT silently lose memory writes. All writes confirmed or logged as failed.
- System MUST NOT corrupt SQLite on partial writes. Use transactions.
- System MUST NOT overwrite existing memory without explicit user confirmation.

### NFR-04 — Inspectability
- All memory files MUST be human-readable without tooling.
- All logs MUST be readable with a text editor or `jq`.
- Database schema MUST be documented.

### NFR-05 — Portability
- System MUST run via Docker Compose on a standard development machine.
- System MUST work on macOS and Linux.

### NFR-06 — Testability
- All core logic (planner, policy engine, schema validation, routing) MUST have unit tests.
- Integration tests MUST cover: command → LLM → schema validation → storage path.
- Tests MUST be runnable with `pytest` with no external dependencies.
- The deterministic planner core (availability, fatigue caps, deadline-risk
  formula) MUST be unit-tested independently of any LLM, and the plan-quality
  rubric MUST run as an automated suite on a seeded fixture week.

### NFR-07 — Time correctness
- A configurable IANA timezone (`TIMEZONE`, default `UTC`) MUST govern all
  wall-clock scheduling math.
- Stored timestamps MUST be UTC ISO 8601; wall-clock fields are interpreted
  in the configured zone.
- Availability, fatigue, and deadline math MUST use the zone's real offset
  for the date in question (DST-correct). Naive local-time arithmetic that
  ignores the zone is a defect, not acceptable behaviour.

---

## Out of Scope for v1

- LMS or calendar integration
- Email integration
- Multi-user support
- Payments
- Mobile app
- Browser automation
- Autonomous shell
- Self-modifying code
- WhatsApp
- Neo4j, Qdrant, PostgreSQL
