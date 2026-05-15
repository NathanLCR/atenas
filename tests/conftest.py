"""Shared pytest fixtures for Atenas Phase 1 tests."""

from pathlib import Path

import pytest

from app.config import Settings
from core.db import init_db
from core.skill_registry import SkillRegistry


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return an initialized temporary SQLite database path."""

    db_path = tmp_path / "data" / "atenas.sqlite"
    init_db(db_path)
    return db_path


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return settings pointing at temporary runtime directories."""

    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        output_dir=tmp_path / "output",
        inbox_dir=tmp_path / "inbox",
        logs_dir=tmp_path / "logs",
    )


@pytest.fixture
def registry() -> SkillRegistry:
    """Return a fresh skill registry."""

    return SkillRegistry()

