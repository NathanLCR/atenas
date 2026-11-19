"""Dashboard labels must describe what the numbers actually are."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.config import Settings
from app.dashboard import _day_label, _minutes_until
from app.main import create_app
from core.demo import seed_demo_data
from core.skill_registry import SkillRegistry


def _client(settings: Settings) -> TestClient:
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    seed_demo_data(settings.db_path, settings.timezone, allowed_file_roots=[settings.inbox_dir])
    return TestClient(create_app(settings=settings, registry=SkillRegistry()))


def test_study_plan_card_reports_planned_not_committed(settings: Settings) -> None:
    with _client(settings) as client:
        text = client.get("/dashboard/").text
    assert "planned this week" in text
    assert "committed this week" not in text
    assert "FREE TO STUDY" in text


def test_stamp_is_configurable_and_neutral_by_default(settings: Settings) -> None:
    with _client(settings) as client:
        text = client.get("/dashboard/week").text
    assert "DBS" not in text and "DUBLIN" not in text
    assert "LOCAL STUDY DESK" in text

    custom = settings.model_copy(
        update={"dashboard_stamp_line1": "MY SCHOOL", "dashboard_stamp_line2": "MY CITY"}
    )
    with TestClient(create_app(settings=custom, registry=SkillRegistry())) as client:
        text = client.get("/dashboard/week").text
    assert "MY SCHOOL" in text and "MY CITY" in text


def test_day_label_names_non_today_blocks() -> None:
    today = date(2026, 11, 16)
    assert _day_label(today, today) == "today"
    assert _day_label(date(2026, 11, 17), today) == "tomorrow"
    assert _day_label(date(2026, 11, 19), today) == "Thu 19 Nov"


def test_minutes_until_ignores_non_datetimes() -> None:
    assert _minutes_until("not-a-datetime", "UTC") is None
