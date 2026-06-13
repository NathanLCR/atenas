"""SQLite connection helpers and schema initialization for Atenas Core."""

from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


SCHEMA_SQL = """
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

-- Phase 6: Knowledge layer tables
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

-- Phase 8: FTS5 virtual table for retrieval full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS retrieval_chunks_fts
USING fts5(chunk_id UNINDEXED, title, text);

-- Agent trace tables (operational metadata)
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

-- Phase 8: Controlled retrieval chunk index
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
"""


@contextmanager
def connect(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    """Context manager that opens, yields, commits/rolls back, and closes."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    """Return a configured SQLite connection with WAL and foreign keys enabled."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    logger.debug(
        "database_connection_opened",
        extra={"event_type": "database_connection_opened", "db_path": str(path)},
    )
    return connection


def init_db(db_path: Path | str) -> None:
    """Create tables and apply backward-compatible migrations.

    Runs SCHEMA_SQL (CREATE TABLE IF NOT EXISTS) and then applies
    column migrations for databases created by earlier phases.
    Safe to call multiple times.
    """
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _apply_phase3_migrations(conn)
        _apply_phase3_indexes(conn)
        _apply_memory_migrations(conn)
    finally:
        conn.close()
    logger.info("database_initialized", extra={"event_type": "database_initialized", "db_path": str(db_path)})


def _apply_phase3_migrations(connection: sqlite3.Connection) -> None:
    """Add Phase 3 scheduling columns to databases created by earlier phases."""

    _ensure_column(connection, "assignments", "due_at", "TEXT")
    _ensure_column(connection, "assignments", "priority_rank", "INTEGER NOT NULL DEFAULT 3")
    _ensure_column(connection, "assignments", "weight", "REAL")
    _ensure_column(connection, "assignments", "estimated_hours", "REAL")
    _ensure_column(connection, "assignments", "completed_hours", "REAL NOT NULL DEFAULT 0")
    _ensure_column(connection, "assignments", "notes", "TEXT")

    _ensure_column(connection, "work_shifts", "title", "TEXT")
    _ensure_column(connection, "work_shifts", "start_at", "TEXT")
    _ensure_column(connection, "work_shifts", "end_at", "TEXT")
    _ensure_column(connection, "work_shifts", "location", "TEXT")
    _ensure_column(connection, "work_shifts", "energy_cost", "INTEGER")

    _ensure_column(connection, "class_sessions", "weekday", "INTEGER")
    _ensure_column(connection, "class_sessions", "active", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(connection, "class_sessions", "notes", "TEXT")


def _apply_phase3_indexes(connection: sqlite3.Connection) -> None:
    """Create indexes that depend on Phase 3 migration columns."""

    connection.execute("CREATE INDEX IF NOT EXISTS idx_assignments_due_at ON assignments(due_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_work_shifts_start_at ON work_shifts(start_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_class_sessions_weekday ON class_sessions(weekday)")


def _apply_memory_migrations(connection: sqlite3.Connection) -> None:
    """Add memory_items columns introduced after initial schema creation."""

    _ensure_column(connection, "memory_items", "sensitive", "INTEGER NOT NULL DEFAULT 0")


VALID_TABLE_NAMES = frozenset({
    "documents", "chunks", "nodes", "edges", "tasks",
    "study_modules", "assignments", "work_shifts",
    "class_sessions", "study_blocks", "memory_items", "llm_calls",
    "notes", "files", "note_file_links", "retrieval_chunks",
    "agent_traces", "agent_trace_steps", "agent_threads",
    "pending_actions",
})


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    """Add a column if it is absent."""

    if table_name not in VALID_TABLE_NAMES:
        raise ValueError(f"Invalid table name: {table_name}")
    if not _IDENTIFIER_RE.match(column_name):
        raise ValueError(f"Invalid column name: {column_name}")
    if not _IDENTIFIER_RE.match(definition.split()[0]):
        raise ValueError(f"Invalid column definition: {definition}")
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
