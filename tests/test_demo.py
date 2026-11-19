"""Demo seeding: `atenas demo` and core.demo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from click.testing import CliRunner

from app.cli import main
from app.config import clear_settings_cache
from core.academic.service import AcademicService
from core.demo import DemoSeedError, seed_demo_data
from core.knowledge.service import KnowledgeService

TZ = ZoneInfo("Europe/Dublin")
NOW = datetime(2026, 11, 16, 8, 30, tzinfo=TZ)  # a Monday


@pytest.fixture
def roots(tmp_path: Path) -> list[Path]:
    root = tmp_path / "inbox"
    root.mkdir()
    return [root]


def test_seed_creates_realistic_week(tmp_path: Path, roots: list[Path]) -> None:
    db = tmp_path / "demo.sqlite"
    summary = seed_demo_data(db, TZ, NOW, allowed_file_roots=roots)
    service = AcademicService(db, TZ)

    assert summary.modules == 4 == len(service.list_modules())
    assert len(service.list_class_sessions()) == summary.classes >= 4
    shifts = service.list_all_work_shifts(limit=100)
    assert 3 <= len(shifts) <= 4
    assert any(s.end_at.hour >= 23 for s in shifts)
    assert {str(s.fatigue_level) for s in shifts} >= {"low", "high"}
    assignments = service.list_all_assignments(include_completed=False)
    assert 5 <= len(assignments) <= 6
    soon = [a for a in assignments if (a.due_at - NOW).total_seconds() < 72 * 3600]
    assert soon and all(a.priority <= 2 for a in soon)
    assert len(KnowledgeService(db, TZ, allowed_file_roots=roots).list_notes(limit=10)) == 3


def test_seeded_data_produces_plan_without_overlaps(tmp_path: Path, roots: list[Path]) -> None:
    db = tmp_path / "demo.sqlite"
    seed_demo_data(db, TZ, NOW, allowed_file_roots=roots)
    service = AcademicService(db, TZ)
    plan = service.get_study_plan(now=NOW)

    assert plan.blocks
    for block in plan.blocks:
        day = block.start_at.date()
        for hard in service._class_blocks_for_day(day) + service._work_blocks_for_day(day):
            assert not (block.start_at < hard.end_at and hard.start_at < block.end_at)


def test_refuses_when_modules_exist_unless_forced(tmp_path: Path, roots: list[Path]) -> None:
    db = tmp_path / "demo.sqlite"
    seed_demo_data(db, TZ, NOW, allowed_file_roots=roots)
    with pytest.raises(DemoSeedError):
        seed_demo_data(db, TZ, NOW, allowed_file_roots=roots)
    assert len(AcademicService(db, TZ).list_modules()) == 4

    seed_demo_data(db, TZ, NOW, force=True, allowed_file_roots=roots)
    assert len(AcademicService(db, TZ).list_modules()) == 8


def test_cli_demo_seeds_and_refuses(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("DATA_DIR", "LOGS_DIR", "MEMORY_DIR", "INBOX_DIR", "OUTPUT_DIR"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    monkeypatch.setenv("KNOWLEDGE_FILE_ROOTS", str(tmp_path / "inbox_dir"))
    clear_settings_cache()
    db = tmp_path / "custom" / "x.sqlite"
    runner = CliRunner()
    try:
        first = runner.invoke(main, ["demo", "--db", str(db)])
        assert first.exit_code == 0, first.output
        assert "4 modules" in first.output
        assert "/dashboard/" in first.output
        again = runner.invoke(main, ["demo", "--db", str(db)])
        assert again.exit_code != 0
        assert "--force" in again.output
        assert runner.invoke(main, ["demo", "--db", str(db), "--force"]).exit_code == 0
    finally:
        clear_settings_cache()
