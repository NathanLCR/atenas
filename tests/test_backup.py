"""Tests for local backup and restore support."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from app.config import Settings
from core.backup import BackupService
from core.db import init_db


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        output_dir=tmp_path / "output",
        inbox_dir=tmp_path / "inbox",
        logs_dir=tmp_path / "logs",
    )


def _manifest(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        return json.loads(archive.read("manifest.json"))


def test_backup_creates_timestamped_archive_under_output_backups(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    archive_path = BackupService(settings).create_backup()

    assert archive_path.exists()
    assert archive_path.parent == settings.output_dir / "backups"
    assert archive_path.name.startswith("atenas-backup-")
    assert archive_path.suffix == ".zip"


def test_manifest_records_paths_hashes_and_excluded_secret_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    settings.memory_dir.mkdir(parents=True)
    (settings.memory_dir / "profile.md").write_text("memory", encoding="utf-8")
    settings.inbox_dir.mkdir(parents=True)
    (settings.inbox_dir / "source.txt").write_text("source", encoding="utf-8")

    archive_path = BackupService(settings).create_backup()
    manifest = _manifest(archive_path)

    assert manifest["version"] == 1
    assert manifest["db_path"] == str(settings.db_path)
    assert manifest["created_at"].endswith("Z")
    assert ".env" in manifest["excluded_secret_paths"]
    included = manifest["included_files"]
    assert included
    for item in included:
        assert item["source_path"]
        assert item["archive_path"]
        assert item["sha256"]
        assert item["size"] >= 0


def test_dotenv_is_excluded_by_default(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=secret", encoding="utf-8")

    archive_path = BackupService(settings, project_root=tmp_path).create_backup()

    with zipfile.ZipFile(archive_path) as archive:
        members = set(archive.namelist())
    assert ".env" not in members
    assert "manifest.json" in members


def test_restore_refuses_to_overwrite_existing_db_without_force(tmp_path: Path) -> None:
    source_settings = _settings(tmp_path / "source")
    init_db(source_settings.db_path)
    archive_path = BackupService(source_settings).create_backup()

    target_settings = _settings(tmp_path / "target")
    init_db(target_settings.db_path)

    with pytest.raises(FileExistsError):
        BackupService(target_settings).restore_backup(archive_path, force=False)
