"""FR-06 study planning acceptance tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.models import TimeBlock
from core.academic.service import AcademicService
from core.db import init_db
from core.schemas import FatigueLevel

TZ = ZoneInfo("Europe/Dublin")
MONDAY = date(2026, 5, 18)
NOW = datetime(2026, 5, 18, 7, 0, tzinfo=TZ)


def test_plan_blocks_stay_inside_authoritative_availability(
    tmp_db: Path,
) -> None:
    service = AcademicService(tmp_db, timezone=TZ)
    service.create_class_session("Lecture", 0, "10:00", "12:00")
    service.create_work_shift(
        "Work",
        datetime(2026, 5, 18, 16, 0, tzinfo=TZ),
        datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
    )
    service.create_assignment(
        "Seeded coursework",
        datetime(2026, 5, 19, 17, 0, tzinfo=TZ),
        priority=1,
        estimated_hours=8,
    )

    availability = service.get_availability(MONDAY, MONDAY, now=NOW)
    plan = service.get_study_plan(reference_date=MONDAY, now=NOW, horizon_days=1)

    assert plan.blocks
    assert all(
        _is_inside_study_window(block, availability.days[0].study_windows)
        for block in plan.blocks
    )
    assert all(
        not _overlaps(block, hard_block)
        for block in plan.blocks
        for hard_block in availability.days[0].blocked
    )
    assert sum(block.minutes for block in plan.blocks) <= availability.days[0].total_study_minutes


def test_high_fatigue_late_shift_prevents_deep_work_before_ten_next_morning(
    tmp_db: Path,
) -> None:
    service = AcademicService(tmp_db, timezone=TZ)
    service.create_work_shift(
        "Late close",
        datetime(2026, 5, 18, 17, 0, tzinfo=TZ),
        datetime(2026, 5, 18, 23, 30, tzinfo=TZ),
        fatigue_level=FatigueLevel.HIGH,
    )
    service.create_assignment(
        "Priority report",
        datetime(2026, 5, 19, 12, 0, tzinfo=TZ),
        priority=1,
        estimated_hours=10,
    )

    plan = service.get_study_plan(reference_date=MONDAY, now=NOW, horizon_days=3)

    early_next_day = [
        block
        for block in plan.blocks
        if block.start_at.date() == date(2026, 5, 19) and block.start_at.hour < 10
    ]
    assert early_next_day
    assert {block.intensity for block in early_next_day} <= {"recovery", "light"}


def test_high_fatigue_work_day_allows_only_light_or_recovery_blocks(
    tmp_db: Path,
) -> None:
    service = AcademicService(tmp_db, timezone=TZ)
    service.create_work_shift(
        "Hard shift",
        datetime(2026, 5, 18, 14, 0, tzinfo=TZ),
        datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
        fatigue_level=FatigueLevel.HIGH,
    )
    service.create_assignment(
        "Same-day prep",
        datetime(2026, 5, 18, 21, 0, tzinfo=TZ),
        priority=1,
        estimated_hours=3,
    )

    plan = service.get_study_plan(reference_date=MONDAY, now=NOW, horizon_days=1)

    same_day_blocks = [
        block for block in plan.blocks if block.start_at.date() == MONDAY
    ]
    assert same_day_blocks
    assert {block.intensity for block in same_day_blocks} <= {"recovery", "light"}


def test_urgent_high_priority_assignment_gets_block_or_warning(
    tmp_db: Path,
) -> None:
    service = AcademicService(tmp_db, timezone=TZ)
    due_at = NOW + timedelta(hours=70)
    urgent = service.create_assignment(
        "Urgent high priority",
        due_at,
        priority=1,
        estimated_hours=3,
    )

    plan = service.get_study_plan(reference_date=MONDAY, now=NOW, horizon_days=4)

    urgent_blocks = [
        block
        for block in plan.blocks
        if block.assignment_id == urgent.id and block.end_at <= due_at
    ]
    urgent_warnings = [
        item
        for item in plan.unscheduled
        if item.assignment_id == urgent.id and item.reason
    ]
    assert urgent_blocks or urgent_warnings


def test_seeded_fixture_week_is_deterministic(tmp_db: Path) -> None:
    service = AcademicService(tmp_db, timezone=TZ)
    service.create_class_session("Lecture", 0, "10:00", "12:00")
    service.create_work_shift(
        "Work",
        datetime(2026, 5, 20, 16, 0, tzinfo=TZ),
        datetime(2026, 5, 20, 22, 0, tzinfo=TZ),
        fatigue_level=FatigueLevel.MEDIUM,
    )
    service.create_assignment(
        "Coursework A",
        datetime(2026, 5, 22, 17, 0, tzinfo=TZ),
        priority=2,
        estimated_hours=5,
    )
    service.create_assignment(
        "Coursework B",
        datetime(2026, 5, 23, 17, 0, tzinfo=TZ),
        priority=1,
        estimated_hours=4,
    )

    first = service.get_study_plan(reference_date=MONDAY, now=NOW, horizon_days=7)
    second = service.get_study_plan(reference_date=MONDAY, now=NOW, horizon_days=7)

    assert first == second


def test_heavy_shift_week_reduces_planned_minutes_by_thirty_percent(
    tmp_path: Path,
) -> None:
    light_service = _service(tmp_path / "light.sqlite")
    heavy_service = _service(tmp_path / "heavy.sqlite")
    for service in (light_service, heavy_service):
        service.create_assignment(
            "Large project",
            datetime(2026, 5, 24, 21, 0, tzinfo=TZ),
            priority=1,
            estimated_hours=80,
        )
    for offset in range(4):
        day = datetime(2026, 5, 18 + offset, 16, 0, tzinfo=TZ)
        heavy_service.create_work_shift(
            "Work",
            day,
            day.replace(hour=20),
            fatigue_level=FatigueLevel.MEDIUM,
        )

    light_plan = light_service.get_study_plan(
        reference_date=MONDAY,
        now=NOW,
        horizon_days=7,
    )
    heavy_plan = heavy_service.get_study_plan(
        reference_date=MONDAY,
        now=NOW,
        horizon_days=7,
    )

    assert heavy_plan.summary.total_planned_minutes <= int(
        light_plan.summary.total_planned_minutes * 0.7
    )


def _service(path: Path) -> AcademicService:
    init_db(path)
    return AcademicService(path, timezone=TZ)


def _is_inside_study_window(block: object, windows: list[object]) -> bool:
    return any(
        window.start_at <= block.start_at and block.end_at <= window.end_at
        for window in windows
    )


def _overlaps(block: object, hard_block: TimeBlock) -> bool:
    return block.start_at < hard_block.end_at and block.end_at > hard_block.start_at
