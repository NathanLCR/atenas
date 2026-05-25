# Atenas — Data Model v0.1

## Storage Architecture

| Layer | Technology | Role |
|---|---|---|
| **Source of truth for v1** | SQLite (`data/atenas.sqlite`) | Academic data, notes/files metadata, memory items, retrieval chunks, traces, and LLM call records |
| **Human-readable files** | Registered files under allowed roots such as `inbox/` and `memory/` | User-provided source material for retrieval; not the canonical store for operational rows in v1 |

SQLite is the v1 operational source of truth. If lost, restore from a database
backup or a future export; the current implementation does not rebuild all user
state from Markdown/YAML files.

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
  local** and interpreted in `settings.timezone` (IANA, e.g.
  `Europe/London`; default `UTC`).
- Every availability/fatigue/deadline computation converts via
  `settings.timezone` and uses the zone's real offset for that date, so DST
  shifts and an international student's relocation do not silently corrupt
  scheduling. Changing `TIMEZONE` re-interprets future scheduling only;
  historical UTC timestamps are unaffected.

---

## Key Design Decisions (corrections from PDF audit)

| Decision | Value | Source |
|---|---|---|
| Primary keys | `TEXT` (UUID strings) | PDF spec |
| fatigue_level | `TEXT` enum: `low`, `medium`, `high` | PDF spec |
| work_shifts.date | Separate `TEXT` column (YYYY-MM-DD) | Added — PDF stores datetime in start_time but range queries need a date column |
| work_shifts.start_time/end_time | `TEXT` HH:MM | PDF spec uses full datetime; we split for clarity |
| Confidence threshold | 0.65 everywhere | PDF spec (was inconsistent across generated specs) |

---

## SQLite Schema v1

Mirrors `core/db.py` `SCHEMA_SQL`, which is the single canonical schema owner.
`core/db.py` also applies backward-compatible column migrations (`due_at`,
`priority_rank`, `weight`, `completed_hours`, `notes`, work-shift `start_at`/
`end_at`/`location`/`energy_cost`, class-session `weekday`/`active`/`notes`,
and `memory_items.sensitive`) for databases created by earlier phases; those
columns are folded into the `CREATE TABLE` statements below. Keep this block in
sync when `SCHEMA_SQL` changes.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL,
    domain      TEXT NOT NULL,
    path        TEXT NOT NULL,
    summary     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id            TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES documents(id),
    chunk_index   INTEGER NOT NULL,
    text          TEXT NOT NULL,
    summary       TEXT,
    section       TEXT,
    page_start    INTEGER,
    page_end      INTEGER,
    embedding_id  TEXT,
    embedding     TEXT,
    embedding_dim INTEGER,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    title       TEXT NOT NULL,
    path        TEXT,
    summary     TEXT,
    importance  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    source_id   TEXT NOT NULL REFERENCES nodes(id),
    relation    TEXT NOT NULL,
    target_id   TEXT NOT NULL REFERENCES nodes(id),
    confidence  REAL NOT NULL DEFAULT 1.0,
    source      TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (source_id, relation, target_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id                 TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT,
    domain             TEXT,
    module_id          TEXT,
    assignment_id      TEXT,
    status             TEXT NOT NULL DEFAULT 'todo',
    priority           TEXT NOT NULL DEFAULT 'medium',
    estimated_minutes  INTEGER,
    due_date           TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_modules (
    id          TEXT PRIMARY KEY,
    code        TEXT,
    name        TEXT NOT NULL,
    lecturer    TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    module_id       TEXT,
    description     TEXT,
    due_date        TEXT,
    due_at          TEXT,
    status          TEXT NOT NULL DEFAULT 'todo',
    priority        TEXT NOT NULL DEFAULT 'medium',
    priority_rank   INTEGER NOT NULL DEFAULT 3,
    weight          REAL,
    estimated_hours REAL,
    completed_hours REAL NOT NULL DEFAULT 0,
    notes           TEXT,
    brief_path      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- CORRECTION: added date column; fatigue_level is TEXT CHECK constraint
CREATE TABLE IF NOT EXISTS work_shifts (
    id               TEXT PRIMARY KEY,
    title            TEXT,
    date             TEXT NOT NULL,
    workplace        TEXT,
    start_time       TEXT NOT NULL,
    end_time         TEXT NOT NULL,
    start_at         TEXT,
    end_at           TEXT,
    location         TEXT,
    role             TEXT,
    energy_cost      INTEGER,
    commute_minutes  INTEGER NOT NULL DEFAULT 0,
    fatigue_level    TEXT NOT NULL DEFAULT 'medium'
                         CHECK(fatigue_level IN ('low', 'medium', 'high')),
    notes            TEXT,
    source           TEXT NOT NULL DEFAULT 'telegram',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS class_sessions (
    id          TEXT PRIMARY KEY,
    module_id   TEXT,
    title       TEXT NOT NULL,
    weekday     INTEGER,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    location    TEXT,
    recurrence  TEXT NOT NULL DEFAULT 'weekly',
    active      INTEGER NOT NULL DEFAULT 1,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_blocks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    date        TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    intensity   TEXT NOT NULL
                    CHECK(intensity IN ('recovery','light','medium','deep')),
    task_id     TEXT,
    module_id   TEXT,
    plan_id     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ADDITION: memory_items table (not in PDF but needed for FR-03)
CREATE TABLE IF NOT EXISTS memory_items (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    summary     TEXT NOT NULL,
    domain      TEXT NOT NULL,
    topic       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    importance  TEXT NOT NULL DEFAULT 'medium',
    source      TEXT NOT NULL DEFAULT 'telegram',
    inferred    INTEGER NOT NULL DEFAULT 1,
    sensitive   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id              TEXT PRIMARY KEY,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    estimated_cost  REAL,
    success         INTEGER NOT NULL,
    latency_ms      INTEGER,
    schema_valid    INTEGER,
    policy_passed   INTEGER,
    outcome         TEXT NOT NULL DEFAULT 'success',
    created_at      TEXT NOT NULL
);
```

Add indexes for common queries:
```sql
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_study_modules_code ON study_modules(code);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_due_date ON assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_work_shifts_date ON work_shifts(date);
CREATE INDEX IF NOT EXISTS idx_study_blocks_date ON study_blocks(date);
CREATE INDEX IF NOT EXISTS idx_memory_items_domain ON memory_items(domain);
CREATE INDEX IF NOT EXISTS idx_memory_items_topic ON memory_items(topic);
CREATE INDEX IF NOT EXISTS idx_llm_calls_task_type ON llm_calls(task_type);
CREATE INDEX IF NOT EXISTS idx_llm_calls_provider ON llm_calls(provider);

-- Knowledge layer tables
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    module_id TEXT NULL,
    assignment_id TEXT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    tags TEXT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (module_id) REFERENCES study_modules(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id)
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    title TEXT NULL,
    description TEXT NULL,
    module_id TEXT NULL,
    assignment_id TEXT NULL,
    file_type TEXT NULL,
    mime_type TEXT NULL,
    size_bytes INTEGER NULL,
    sha256 TEXT NULL,
    tags TEXT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (module_id) REFERENCES study_modules(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id)
);

CREATE TABLE IF NOT EXISTS note_file_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(note_id, file_id),
    FOREIGN KEY (note_id) REFERENCES notes(id),
    FOREIGN KEY (file_id) REFERENCES files(id)
);

CREATE INDEX IF NOT EXISTS idx_notes_archived ON notes(archived);
CREATE INDEX IF NOT EXISTS idx_notes_module ON notes(module_id);
CREATE INDEX IF NOT EXISTS idx_files_archived ON files(archived);
CREATE INDEX IF NOT EXISTS idx_files_module ON files(module_id);

-- FTS5 virtual table for retrieval full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS retrieval_chunks_fts
USING fts5(chunk_id UNINDEXED, title, text);

-- Agent trace tables (operational metadata, no full prompt/note/file bodies)
CREATE TABLE IF NOT EXISTS agent_traces (
    id TEXT PRIMARY KEY,
    actor_user_id INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    model TEXT,
    status TEXT NOT NULL,
    user_message_summary TEXT NOT NULL,
    final_message_summary TEXT,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    pending_action_type TEXT,
    latency_ms INTEGER,
    error TEXT
);

CREATE TABLE IF NOT EXISTS agent_trace_steps (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES agent_traces(id),
    step_index INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_summary TEXT NOT NULL,
    ok INTEGER NOT NULL,
    executed INTEGER NOT NULL,
    pending INTEGER NOT NULL,
    message_summary TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_traces_started ON agent_traces(started_at);
CREATE INDEX IF NOT EXISTS idx_agent_traces_status ON agent_traces(status);
CREATE INDEX IF NOT EXISTS idx_agent_trace_steps_trace ON agent_trace_steps(trace_id);

-- Agent runtime state
CREATE TABLE IF NOT EXISTS agent_threads (
    id TEXT PRIMARY KEY,
    actor_user_id INTEGER NOT NULL,
    channel TEXT NOT NULL DEFAULT 'telegram',
    status TEXT NOT NULL DEFAULT 'active',
    conversation_json TEXT NOT NULL DEFAULT '[]',
    selected_tools_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES agent_threads(id),
    actor_user_id INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    confirmation_message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_threads_actor
ON agent_threads(actor_user_id, channel, status);

CREATE INDEX IF NOT EXISTS idx_pending_actions_actor_status
ON pending_actions(actor_user_id, status, created_at);

-- Controlled retrieval chunk index
CREATE TABLE IF NOT EXISTS retrieval_chunks (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL CHECK(source_kind IN ('note', 'file')),
    source_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    module_id TEXT NULL,
    assignment_id TEXT NULL,
    updated_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    UNIQUE(source_kind, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_source
ON retrieval_chunks(source_kind, source_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_module
ON retrieval_chunks(module_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_assignment
ON retrieval_chunks(assignment_id);

-- Migration indexes applied by core/db.py for the folded-in columns
CREATE INDEX IF NOT EXISTS idx_assignments_due_at ON assignments(due_at);
CREATE INDEX IF NOT EXISTS idx_work_shifts_start_at ON work_shifts(start_at);
CREATE INDEX IF NOT EXISTS idx_class_sessions_weekday ON class_sessions(weekday);
```

---

## FTS5 Retrieval

Retrieval uses SQLite FTS5 for full-text search with BM25 ranking, falling back
to deterministic lexical scoring when FTS5 is unavailable or the MATCH query
fails. The `retrieval_chunks_fts` virtual table mirrors `retrieval_chunks` and
is kept in sync during rebuild, replace_source, and delete_stale_sources
operations.

---

## Semantic Search Storage Design

Decision for v1 (single-user scale): **no external vector store** (Qdrant is
out of scope, SQLite has no native vector type).

- Each chunk's embedding is stored on the `chunks` row as `embedding` =
  JSON-encoded `list[float]`, with `embedding_dim` recording the vector
  length. `embedding_id` is reserved for a future external store and stays
  null in v1.
- Retrieval is **brute-force cosine** computed in Python over the candidate
  chunk set (optionally pre-filtered by `document_id`/`section`). At
  single-user scale (thousands of chunks, not millions) this is well within
  the NFR-02 budget; a linear scan of ~10k 768-dim vectors is tens of ms.
- **Documented ceiling:** if total chunks exceed ~50k, revisit (add an ANN
  index or `sqlite-vec`). That is a post-v1 concern, explicitly noted so the
  decision is not silently outgrown.
- Embedding model: Ollama `nomic-embed-text` (config
  `OLLAMA_EMBEDDING_MODEL`). Built in Phase 10, after Phase 9 chunking.

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
Concept     ──appears_in──►  Module
```

---

## YAML File Formats

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
