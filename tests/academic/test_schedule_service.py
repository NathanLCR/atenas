"""Overview service tests for deterministic Phase 3 scheduling."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.service import AcademicService

TZ = ZoneInfo("Europe/Dublin")


def test_today_overview_includes_classes_work_deadlines_and_availability(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_class_session("Morning Lecture", 0, "10:00", "12:00")
    service.create_work_shift(
        "Evening Shift",
        datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
        datetime(2026, 5, 18, 21, 0, tzinfo=TZ),
    )
    service.create_assignment(
        "Demo Deadline",
        datetime(2026, 5, 21, 17, 0, tzinfo=TZ),
        priority=2,
    )

    overview = service.get_today_overview(now=datetime(2026, 5, 18, 7, 0, tzinfo=TZ))

    assert overview.date == date(2026, 5, 18)
    assert [block.title for block in overview.classes] == ["Morning Lecture"]
    assert [block.title for block in overview.work_shifts] == ["Evening Shift"]
    assert [assignment.title for assignment in overview.deadlines] == ["Demo Deadline"]
    assert overview.availability.total_study_minutes == 9 * 60


def test_week_overview_counts_records_and_deadlines(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_class_session("Morning Lecture", 0, "10:00", "12:00")
    service.create_class_session("Lab", 2, "14:00", "16:00")
    service.create_work_shift(
        "Demo Shift",
        datetime(2026, 5, 19, 14, 0, tzinfo=TZ),
        datetime(2026, 5, 19, 18, 0, tzinfo=TZ),
    )
    service.create_assignment("This Week", datetime(2026, 5, 21, 17, 0, tzinfo=TZ))
    service.create_assignment("Next Week", datetime(2026, 5, 25, 17, 0, tzinfo=TZ))

    overview = service.get_week_overview(
        reference_date=date(2026, 5, 18),
        now=datetime(2026, 5, 18, 7, 0, tzinfo=TZ),
    )

    assert overview.class_count == 2
    assert overview.work_shift_count == 1
    assert overview.open_deadline_count == 1
    assert len(overview.day_summaries) == 7
