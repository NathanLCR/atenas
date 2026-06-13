"""WP4 acceptance tests: SQLite connection lifecycle and WAL-safe backup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.db import connect, init_db


# ---------------------------------------------------------------------------
# WP4.2 — connect() closes the connection after the block
# ---------------------------------------------------------------------------

def test_connect_closes_connection_after_block(tmp_path: Path) -> None:
    """The connection must be closed (unusable) after the with-block exits."""
    db_path = tmp_path / "test.sqlite"
    init_db(db_path)

    with connect(db_path) as conn:
        captured = conn

    with pytest.raises(Exception):
        captured.execute("SELECT 1")


def test_connect_commits_on_clean_exit(tmp_path: Path) -> None:
    """Writes inside connect() must be durable after the block exits."""
    db_path = tmp_path / "test.sqlite"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO study_modules (id, name, created_at, updated_at) "
            "VALUES ('m1', 'Test', '2026-06-12T00:00:00Z', '2026-06-12T00:00:00Z')"
        )

    with connect(db_path) as conn:
        row = conn.execute("SELECT name FROM study_modules WHERE id='m1'").fetchone()
    assert row is not None
    assert row["name"] == "Test"


def test_connect_rolls_back_on_exception(tmp_path: Path) -> None:
    """An exception inside connect() must roll back pending writes."""
    db_path = tmp_path / "test.sqlite"
    init_db(db_path)

    with pytest.raises(RuntimeError):
        with connect(db_path) as conn:
            conn.execute(
                "INSERT INTO study_modules (id, name, created_at, updated_at) "
                "VALUES ('m2', 'RollMe', '2026-06-12T00:00:00Z', '2026-06-12T00:00:00Z')"
            )
            raise RuntimeError("boom")

    with connect(db_path) as conn:
        row = conn.execute("SELECT id FROM study_modules WHERE id='m2'").fetchone()
    assert row is None


# ---------------------------------------------------------------------------
# WP4.3 — backup captures un-checkpointed WAL content
# ---------------------------------------------------------------------------

def test_backup_captures_wal_uncommitted_rows(tmp_path: Path) -> None:
    """Backup must include rows written in WAL-mode before checkpoint."""
    from app.config import Settings
    from core.backup import BackupService

    db_path = tmp_path / "data" / "atenas.sqlite"
    init_db(db_path)

    src = sqlite3.connect(str(db_path))
    src.execute("PRAGMA journal_mode=WAL")
    src.execute(
        "INSERT INTO study_modules (id, name, created_at, updated_at) "
        "VALUES ('wal1', 'WALRow', '2026-06-12T00:00:00Z', '2026-06-12T00:00:00Z')"
    )
    src.commit()

    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        memory_dir=tmp_path / "memory",
        inbox_dir=tmp_path / "inbox",
        logs_dir=tmp_path / "logs",
    )
    service = BackupService(settings)
    archive_path = service.create_backup()

    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    restore_settings = Settings(
        _env_file=None,
        data_dir=restore_dir / "data",
        output_dir=tmp_path / "output2",
        memory_dir=tmp_path / "memory2",
        inbox_dir=tmp_path / "inbox2",
        logs_dir=tmp_path / "logs2",
    )
    restore_service = BackupService(restore_settings)
    restore_service.restore_backup(archive_path, force=True)

    src.close()

    restored_db = restore_dir / "data" / "atenas.sqlite"
    assert restored_db.exists(), "Restored db must exist"
    check = sqlite3.connect(str(restored_db))
    check.row_factory = sqlite3.Row
    row = check.execute("SELECT name FROM study_modules WHERE id='wal1'").fetchone()
    check.close()
    assert row is not None, "WAL row must be present in restored backup"
    assert row["name"] == "WALRow"
