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


def test_get_connection_uses_sqlite_row_factory(tmp_db: Path) -> None:
    """get_connection should return rows addressable by column name."""

    connection = get_connection(tmp_db)
    try:
        assert connection.row_factory is sqlite3.Row
        row = connection.execute("SELECT 1 AS value").fetchone()
        assert row["value"] == 1
    finally:
        connection.close()

