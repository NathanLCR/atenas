"""Availability calculation tests for Phase 3 scheduling."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.service import AcademicService

TZ = ZoneInfo("Europe/Dublin")
MONDAY = date(2026, 5, 18)


def test_empty_week_returns_default_daily_availability(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    availability = service.get_availability(MONDAY, date(2026, 5, 24))

    assert len(availability.days) == 7
    assert [day.total_study_minutes for day in availability.days] == [14 * 60] * 7
    assert availability.total_study_minutes == 7 * 14 * 60


def test_classes_block_study_windows(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_class_session("Demo Lecture", 0, "10:00", "12:00")

    day = service.get_availability(MONDAY, MONDAY).days[0]

    assert [(window.start_at.hour, window.end_at.hour) for window in day.study_windows] == [
        (8, 10),
        (12, 22),
    ]
    assert day.total_study_minutes == 12 * 60


def test_work_shifts_block_study_windows(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_work_shift(
        "Demo Shift",
        datetime(2026, 5, 19, 14, 0, tzinfo=TZ),
        datetime(2026, 5, 19, 18, 0, tzinfo=TZ),
    )

    day = service.get_availability(date(2026, 5, 19), date(2026, 5, 19)).days[0]

    assert day.total_study_minutes == 10 * 60
    assert day.study_windows[0].start_at.hour == 8
    assert day.study_windows[1].start_at.hour == 18


def test_overlapping_class_and_work_blocks_are_merged(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_class_session("Demo Lecture", 0, "10:00", "12:00")
    service.create_work_shift(
        "Demo Shift",
        datetime(2026, 5, 18, 11, 0, tzinfo=TZ),
        datetime(2026, 5, 18, 13, 0, tzinfo=TZ),
    )

    day = service.get_availability(MONDAY, MONDAY).days[0]

    assert len(day.blocked) == 1
    assert day.blocked[0].start_at.hour == 10
    assert day.blocked[0].end_at.hour == 13
    assert day.total_study_minutes == 11 * 60


def test_windows_below_minimum_length_are_filtered_out(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_class_session("Long Seminar", 0, "08:30", "21:30")

    day = service.get_availability(MONDAY, MONDAY).days[0]

    assert day.study_windows == []
    assert day.total_study_minutes == 0


def test_today_excludes_past_time_when_now_is_supplied(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    day = service.get_availability(
        MONDAY,
        MONDAY,
        now=datetime(2026, 5, 18, 12, 30, tzinfo=TZ),
    ).days[0]

    assert day.study_windows[0].start_at.hour == 12
    assert day.study_windows[0].start_at.minute == 30
    assert day.total_study_minutes == 9 * 60 + 30


def test_total_study_minutes_are_calculated_correctly(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_class_session("Morning Lecture", 0, "09:00", "10:30")
    service.create_work_shift(
        "Evening Shift",
        datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
        datetime(2026, 5, 18, 22, 0, tzinfo=TZ),
    )

    day = service.get_availability(MONDAY, MONDAY).days[0]

    assert day.total_study_minutes == (60 + 450)


def test_week_overview_uses_monday_to_sunday_bounds(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    overview = service.get_week_overview(
        reference_date=date(2026, 5, 20),
        now=datetime(2026, 5, 20, 7, 0, tzinfo=TZ),
    )

    assert overview.start_date == MONDAY
    assert overview.end_date == date(2026, 5, 24)
