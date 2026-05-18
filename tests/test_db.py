"""Tests for SQLite initialization and connection helpers."""

import sqlite3
from pathlib import Path

from core.db import get_connection, init_db

EXPECTED_TABLES = {
    "documents",
    "chunks",
    "nodes",
    "edges",
    "tasks",
    "study_modules",
    "assignments",
    "work_shifts",
    "class_sessions",
    "study_blocks",
    "memory_items",
    "llm_calls",
}


def test_init_db_creates_all_tables(tmp_path: Path) -> None:
    """init_db should create every table from the data model."""

    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    assert EXPECTED_TABLES.issubset({row["name"] for row in rows})


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    """Calling init_db repeatedly should be safe."""

    db_path = tmp_path / "atenas.sqlite"

    init_db(db_path)
    init_db(db_path)

    with get_connection(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM sqlite_master WHERE type = 'table'"
        ).fetchone()["count"]

    assert count >= len(EXPECTED_TABLES)


def test_init_db_migrates_phase2_tables_before_phase3_indexes(tmp_path: Path) -> None:
    """Existing Phase 2 tables should gain Phase 3 columns before indexes are built."""

    db_path = tmp_path / "atenas.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE assignments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                module_id TEXT,
                description TEXT,
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'not_started',
                priority TEXT NOT NULL DEFAULT 'medium',
                brief_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE work_shifts (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                workplace TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                role TEXT,
                commute_minutes INTEGER NOT NULL DEFAULT 0,
                fatigue_level TEXT NOT NULL DEFAULT 'medium',
                notes TEXT,
                source TEXT NOT NULL DEFAULT 'telegram',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE class_sessions (
                id TEXT PRIMARY KEY,
                module_id TEXT NOT NULL,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT,
                recurrence TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    init_db(db_path)

    with get_connection(db_path) as connection:
        assignment_columns = _column_names(connection, "assignments")
        work_columns = _column_names(connection, "work_shifts")
        class_columns = _column_names(connection, "class_sessions")
        indexes = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert {"due_at", "priority_rank", "estimated_hours", "completed_hours"}.issubset(
        assignment_columns
    )
    assert {"start_at", "end_at", "energy_cost"}.issubset(work_columns)
    assert {"weekday", "active", "notes"}.issubset(class_columns)
    assert "idx_assignments_due_at" in indexes
    assert "idx_work_shifts_start_at" in indexes
    assert "idx_class_sessions_weekday" in indexes


def test_get_connection_uses_sqlite_row_factory(tmp_db: Path) -> None:
    """get_connection should return rows addressable by column name."""

    connection = get_connection(tmp_db)
    try:
        assert connection.row_factory is sqlite3.Row
        row = connection.execute("SELECT 1 AS value").fetchone()
        assert row["value"] == 1
    finally:
        connection.close()


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    """Return column names for a SQLite table."""

    return {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
