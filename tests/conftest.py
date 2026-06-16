"""Shared pytest fixtures for Atenas Phase 1 tests."""

from pathlib import Path

import pytest

from app.config import Settings
from core.db import init_db
from core.skill_registry import SkillRegistry
from core.utils import ensure_runtime_directories


@pytest.fixture(autouse=True, scope="session")
def _ensure_default_file_roots() -> None:
    """Create the default file roots services fall back to (inbox, memory).

    Several services default ``allowed_file_roots`` to ``[inbox, memory]``
    relative to the working directory, and ``PathPolicy`` rejects a config
    with no existing root. These directories are gitignored, so a fresh
    checkout lacks them and the suite would fail at import-time service
    construction. Creating them mirrors the runtime bootstrap done by app
    startup and ``atenas doctor``.
    """

    defaults = Settings(_env_file=None).knowledge_file_roots
    ensure_runtime_directories(defaults)


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

