"""SQLite connection helpers and schema initialization for Atenas Core."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


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
"""


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    """Return a configured SQLite connection with WAL and foreign keys enabled."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    logger.info(
        "database_connection_opened",
        extra={"event_type": "database_connection_opened", "db_path": str(path)},
    )
    return connection


def init_db(db_path: Path | str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    logger.info("database_initialized", extra={"event_type": "database_initialized", "db_path": str(path)})

