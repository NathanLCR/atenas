"""Repository and service tests for Phase 3 academic records."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from core.academic.models import AssignmentStatus
from core.academic.service import AcademicService

TZ = ZoneInfo("Europe/Dublin")


def test_can_create_and_list_modules(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    module = service.create_module(name="Demo Systems", code="CS100")

    modules = service.list_modules()
    assert modules == [module]
    assert modules[0].name == "Demo Systems"


def test_can_create_and_list_class_sessions(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    session = service.create_class_session(
        title="Demo Lecture",
        weekday=0,
        start_time="10:00",
        end_time="12:00",
    )

    assert service.list_class_sessions() == [session]


def test_invalid_class_weekday_is_rejected(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    with pytest.raises(ValidationError):
        service.create_class_session(
            title="Impossible Lecture",
            weekday=7,
            start_time="10:00",
            end_time="12:00",
        )


def test_invalid_class_time_range_is_rejected(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    with pytest.raises(ValidationError):
        service.create_class_session(
            title="Backwards Lecture",
            weekday=1,
            start_time="12:00",
            end_time="10:00",
        )


def test_can_create_and_list_work_shifts(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    shift = service.create_work_shift(
        title="Demo Shift",
        start_at=datetime(2026, 5, 19, 14, 0, tzinfo=TZ),
        end_at=datetime(2026, 5, 19, 18, 0, tzinfo=TZ),
        energy_cost=3,
    )

    assert service.list_work_shifts() == [shift]


def test_invalid_work_shift_range_is_rejected(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    with pytest.raises(ValidationError):
        service.create_work_shift(
            title="Backwards Shift",
            start_at=datetime(2026, 5, 19, 18, 0, tzinfo=TZ),
            end_at=datetime(2026, 5, 19, 14, 0, tzinfo=TZ),
        )


def test_can_create_and_list_assignments(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)

    assignment = service.create_assignment(
        title="Demo Essay",
        due_at=datetime(2026, 5, 21, 17, 0, tzinfo=TZ),
        priority=2,
        estimated_hours=6,
        completed_hours=1.5,
    )

    assert service.list_upcoming_assignments() == [assignment]
    assert service.list_upcoming_assignments()[0].completed_hours == 1.5


def test_completed_assignments_are_excluded_by_default(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_assignment(
        title="Submitted Essay",
        due_at=datetime(2026, 5, 21, 17, 0, tzinfo=TZ),
        status=AssignmentStatus.SUBMITTED,
    )
    open_assignment = service.create_assignment(
        title="Open Essay",
        due_at=datetime(2026, 5, 22, 17, 0, tzinfo=TZ),
    )

    assert service.list_upcoming_assignments() == [open_assignment]
    assert len(service.list_upcoming_assignments(include_completed=True)) == 2


def test_deadlines_sort_by_due_date_then_priority(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_assignment(
        title="Later high priority",
        due_at=datetime(2026, 5, 25, 12, 0, tzinfo=TZ),
        priority=1,
    )
    same_day_low = service.create_assignment(
        title="Same day low priority",
        due_at=datetime(2026, 5, 21, 12, 0, tzinfo=TZ),
        priority=4,
    )
    same_day_high = service.create_assignment(
        title="Same day high priority",
        due_at=datetime(2026, 5, 21, 12, 0, tzinfo=TZ),
        priority=1,
    )

    assignments = service.list_upcoming_assignments()

    assert assignments[:3] == [same_day_high, same_day_low, assignments[2]]
    assert assignments[2].title == "Later high priority"
