# Atenas — Data Model v0.1

## Storage Architecture

| Layer | Technology | Role |
|---|---|---|
| **Source of truth** | Markdown / YAML files in `memory/` | Human-readable, user-owned |
| **Operational store** | SQLite (`data/atenas.sqlite`) | Fast queries, metadata, logs, graph |

SQLite is always a derivative of the filesystem. If lost, rebuild from `memory/` files.

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

Directly from PDF spec with corrections noted.

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
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents(id),
    chunk_index  INTEGER NOT NULL,
    text         TEXT NOT NULL,
    summary      TEXT,
    section      TEXT,
    page_start   INTEGER,
    page_end     INTEGER,
    embedding_id TEXT,
    created_at   TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS assignments (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    module_id   TEXT,
    description TEXT,
    due_date    TEXT,
    status      TEXT NOT NULL DEFAULT 'not_started',
    priority    TEXT NOT NULL DEFAULT 'medium',
    brief_path  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- CORRECTION: added date column; fatigue_level is TEXT CHECK constraint
CREATE TABLE IF NOT EXISTS work_shifts (
    id               TEXT PRIMARY KEY,
    date             TEXT NOT NULL,
    workplace        TEXT,
    start_time       TEXT NOT NULL,
    end_time         TEXT NOT NULL,
    role             TEXT,
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
    module_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    location    TEXT,
    recurrence  TEXT,
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
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_due_date ON assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_work_shifts_date ON work_shifts(date);
CREATE INDEX IF NOT EXISTS idx_study_blocks_date ON study_blocks(date);
CREATE INDEX IF NOT EXISTS idx_memory_items_domain ON memory_items(domain);
CREATE INDEX IF NOT EXISTS idx_memory_items_topic ON memory_items(topic);
CREATE INDEX IF NOT EXISTS idx_llm_calls_task_type ON llm_calls(task_type);
CREATE INDEX IF NOT EXISTS idx_llm_calls_provider ON llm_calls(provider);
```

---

## Graph Ontology (from PDF)

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
    module: "CS7045"
    deadline: "2024-11-20T23:59:00"
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
