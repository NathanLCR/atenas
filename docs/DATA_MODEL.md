# Atenas — Data Model

## Status

Refreshed against the implementation on 2026-06-12. The canonical SQLite
schema owner is `core/db.py` (`SCHEMA_SQL` plus its migration helpers). This
document summarizes that schema and records storage decisions; it does not
duplicate the full DDL. If this summary and `core/db.py` disagree, `core/db.py`
wins and this file must be updated.

## Storage Architecture

| Layer | Technology | Role |
|---|---|---|
| **Source of truth for v1** | SQLite (`data/atenas.sqlite`) | Academic data, notes/files metadata, memory items, retrieval chunks, agent threads, pending actions, traces, and LLM call records |
| **Human-readable files** | Registered files under allowed roots such as `inbox/` and `memory/` | User-provided source material for retrieval; not the canonical store for operational rows in v1 |

SQLite is the v1 operational source of truth. If lost, restore from a database
backup (`atenas backup` / `atenas restore`) or a future export; the current
implementation does not rebuild all user state from Markdown/YAML files.

---

## Deferred Markdown/YAML Source-Of-Truth Protocol

The original design proposed Markdown/YAML files in `memory/` as canonical and
SQLite as a derived cache. That is **not** the v1 implementation. To make
Markdown/YAML canonical in a later release, Atenas must first implement the
following protocol:

1. **YAML/Markdown files are canonical. SQLite is a derived cache.** On any
   disagreement, the file wins. SQLite is never the only copy of user data.
2. **One write path.** Skills and the dashboard never write SQLite directly.
   Both call the same skill write function, which performs an atomic logical
   write: (a) write/replace the YAML region, (b) upsert the SQLite row, in
   that order, in one operation. If (b) fails, the file is still correct and
   the row is re-derivable; the failure is logged (NFR-03), not swallowed.
3. **Reconciliation on startup and on demand.** Each canonical file tracks an
   `updated_at`. On startup, and via an admin `reindex` action, Atenas
   compares file `updated_at` / mtime against the last index marker; any file
   newer than its derived rows triggers a re-derive of just those rows.
   This is how hand-edits to YAML are absorbed.
4. **Rebuild is specified, not hand-waved.** `reindex(scope)` truncates the
   derived tables in scope and rebuilds them by parsing the canonical files.
   It is idempotent and safe to run anytime. Logs/`llm_calls` are *not*
   derived and are never truncated by reindex.
5. **Conflict policy.** If a file is malformed, the reindex for that scope
   aborts with a logged error and the previous derived rows are kept (stale
   but consistent) rather than partially applied. The user is told which
   file failed to parse.
6. **No dual ownership of a field.** A field is owned by exactly one file.
   Derived/computed values (e.g. `deadline_risk`) live only in SQLite and are
   recomputed, never hand-edited.

Until that protocol exists in code and tests, contributors must treat SQLite as
canonical for v1 and avoid docs or features that assume a file-backed rebuild is
available.

---

## Time & Timezone

- All stored `created_at`/`updated_at` are UTC ISO 8601 (`utc_now()`).
- All wall-clock fields (`date`, `start_time`, `end_time`) are **naive
  local** and interpreted in `settings.timezone` (IANA; the configured
  default is `Europe/Dublin` in `app/config.py`).
- Every availability/fatigue/deadline computation converts via
  `settings.timezone` and uses the zone's real offset for that date, so DST
  shifts and an international student's relocation do not silently corrupt
  scheduling. Changing `TIMEZONE` re-interprets future scheduling only;
  historical UTC timestamps are unaffected.

---

## Key Design Decisions

| Decision | Value | Note |
|---|---|---|
| Schema owner | `core/db.py` `SCHEMA_SQL` + `_apply_*_migrations` | One canonical DDL location; no duplicate schema definitions |
| Primary keys | `TEXT` (UUID strings) for domain tables; `INTEGER AUTOINCREMENT` for `notes`/`files`/`note_file_links` | Knowledge tables predate the UUID convention and keep integer IDs |
| fatigue_level | `TEXT` enum: `low`, `medium`, `high` with CHECK constraint | |
| work_shifts datetimes | `start_at`/`end_at` ISO datetimes are the live fields; legacy `date`/`start_time`/`end_time` columns remain for backward compatibility | |
| assignments deadlines | `due_at` ISO datetime is the live field; legacy `due_date` remains | |
| assignments priority | `priority_rank INTEGER 1–5` is the live field; legacy `priority TEXT` remains | |
| Confidence threshold | 0.65 everywhere | Secondary signal only — see `docs/SCHEMAS.md` conventions |

---

## SQLite Schema v1 — Table Summary

Full DDL lives in `core/db.py`. Tables by concern:

### Academic

- `study_modules` — module catalog (`id`, `code`, `name`, `lecturer`, `notes`).
- `assignments` — assignment tracking (`id`, `title`, `module_id`,
  `description`, `due_date` legacy, `due_at`, `status` default `'todo'`,
  `priority` legacy, `priority_rank` default `3`, `weight`,
  `estimated_hours`, `completed_hours`, `notes`, `brief_path`).
- `work_shifts` — work shifts (`id`, `title`, `date`, `workplace`,
  `start_time`/`end_time` legacy, `start_at`/`end_at`, `location`, `role`,
  `energy_cost`, `commute_minutes`, `fatigue_level` CHECK low/medium/high,
  `notes`, `source`).
- `class_sessions` — recurring classes (`id`, `module_id` nullable, `title`,
  `weekday` 0–6, `start_time`, `end_time`, `location`, `recurrence`,
  `active`, `notes`).
- `study_blocks` — planned study blocks (`id`, `title`, `date`,
  `start_time`, `end_time`, `intensity` CHECK recovery/light/medium/deep,
  `task_id`, `module_id`, `plan_id`).
- `tasks` — sub-assignment tasks (`id`, `title`, `description`, `domain`,
  `module_id`, `assignment_id`, `status`, `priority`, `estimated_minutes`,
  `due_date`).

### Knowledge and retrieval

- `notes` — user notes (`id` INTEGER, `title`, `body`, `module_id`,
  `assignment_id`, `source_type`, `tags`, `archived`).
- `files` — registered local files (`id` INTEGER, `path`, `filename`,
  `title`, `description`, `module_id`, `assignment_id`, `file_type`,
  `mime_type`, `size_bytes`, `sha256`, `tags`, `archived`).
- `note_file_links` — note↔file links (unique `note_id`+`file_id`).
- `retrieval_chunks` — indexed text chunks (`id`, `source_kind`
  CHECK note/file, `source_id`, `chunk_index`, `title`, `text`,
  `module_id`, `assignment_id`, `updated_at`, `indexed_at`; unique
  source_kind+source_id+chunk_index).
- `retrieval_chunks_fts` — FTS5 virtual table mirroring `retrieval_chunks`
  (`chunk_id` unindexed, `title`, `text`).
- `documents` / `chunks` — reserved document-ingestion tables with an
  `embedding` column reserved for a post-v1 embedding store. **No v1 code
  writes embeddings**; see "Search Ranking Design" below.

### Memory

- `memory_items` — persistent user memory (`id`, `content`, `summary`,
  `domain`, `topic`, `tags` JSON, `importance`, `source`, `inferred`,
  `sensitive`, timestamps).

### Agent runtime

- `agent_threads` — durable conversation state per actor/channel (`id`,
  `actor_user_id`, `channel`, `status`, `conversation_json`,
  `selected_tools_json`).
- `pending_actions` — durable confirm-first proposals (`id`, `thread_id`,
  `actor_user_id`, `tool_name`, `action_type`, `proposal_json`,
  `confirmation_message`, `status` pending/executed/cancelled/expired,
  `expires_at`).
- `agent_traces` / `agent_trace_steps` — operational trace metadata
  (summaries only; no full prompt/note/file bodies).

### Audit

- `llm_calls` — LLM call records (`provider`, `model`, `task_type`, token
  counts, `estimated_cost`, `success`, `latency_ms`, `schema_valid`,
  `policy_passed`, `outcome`).

### Reserved (no v1 consumer)

- `nodes` / `edges` — graph ontology tables, deferred to post-v1 (below).

Backward-compatible column migrations for databases created by earlier phases
are applied in `core/db.py` (`_apply_phase3_migrations`,
`_apply_memory_migrations`).

---

## FTS5 Retrieval

Retrieval uses SQLite FTS5 for full-text search with BM25 ranking, falling back
to deterministic lexical scoring when FTS5 is unavailable or the MATCH query
fails. The `retrieval_chunks_fts` virtual table mirrors `retrieval_chunks` and
is kept in sync during rebuild, replace_source, and delete_stale_sources
operations.

---

## Search Ranking Design

**v1 decision (implemented):** retrieval ranking is FTS5/BM25 with a
deterministic sparse lexical fallback (`core/retrieval/embeddings.py` provides
tokenization and lexical scoring only — despite the module name, it computes no
vector embeddings). There is no vector store, no embedding generation, and no
cosine similarity in v1.

**Post-v1 option (not implemented):** semantic search via per-chunk embeddings.
The reserved design, recorded for when a concrete need arises:

- Store each chunk's embedding on the `chunks` row as JSON-encoded
  `list[float]` with `embedding_dim`; `embedding_id` stays reserved for a
  future external store.
- Brute-force cosine in Python over the candidate set is acceptable at
  single-user scale; revisit with an ANN index or `sqlite-vec` past ~50k
  chunks.
- Candidate embedding model: Ollama `nomic-embed-text`
  (`OLLAMA_EMBEDDING_MODEL` config exists but is unused in v1).

No doc or feature may assume semantic search exists until this lands in code
and tests.

---

## Graph Ontology — DEFERRED to post-v1

The `nodes`/`edges` tables ship in the schema as **reserved structure with
no v1 consumer**. No v1 phase builds or queries the graph; it had no defined
question it answers that the relational tables + retrieval cannot. It is
kept (cheap, empty) only to avoid a later migration, and is explicitly out
of v1 scope to prevent speculative complexity. The ontology below is recorded
for when a concrete need arises — not a v1 deliverable.

**Node types:** student, module, class_session, work_shift, assignment, deadline, task, study_block, paper, note, concept, file, skill, decision, weekly_plan, daily_plan

**Edge types:** belongs_to, related_to, depends_on, supports, contradicts, mentions, uses, produces, requires_action, scheduled_for, blocks_time, reduces_capacity, derived_from, decided_because

---

## Key Relationships

```
Assignment  ──belongs_to──►  Module
Task        ──belongs_to──►  Assignment
Task        ──scheduled_for──►  StudyBlock
WorkShift   ──blocks_time──►  AvailabilityBlock
ClassSession ──blocks_time──►  AvailabilityBlock
StudyBlock  ──part_of──►  DailyPlan
Paper       ──supports──►  Assignment
Chunk       ──belongs_to──►  Paper
Note        ──derived_from──►  Paper
```

---

## YAML File Formats (deferred protocol examples)

These formats belong to the deferred Markdown/YAML source-of-truth protocol
above. They are not read or written by v1 code.

### `memory/work/shifts.yaml`
```yaml
shifts:
  - id: "a1b2c3d4-..."
    date: "2024-11-04"
    start_time: "18:00"
    end_time: "23:30"
    workplace: "The Anchor Pub"
    fatigue_level: "high"
    commute_minutes: 25
    source: "telegram"
```

### `memory/assignments/active.yaml`
```yaml
assignments:
  - id: "e5f6g7h8-..."
    title: "Literature Review — AI in Education"
    module_id: "CS7045"
    due_date: "2024-11-20T23:59:00"
    estimated_hours: 12
    priority: "high"
    status: "in_progress"
    tasks:
      - title: "Collect 10 papers"
        estimated_minutes: 90
        status: "done"
      - title: "Write section 1"
        estimated_minutes: 120
        status: "todo"
```
