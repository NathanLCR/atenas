"""Tests for Phase 9 notification service."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from core.academic.models import AssignmentStatus
from core.notifications.models import DeadlineAlert, OverdueAlert, StudyBlockReminder
from core.notifications.service import NotificationService, seconds_until, seconds_until_weekday

TZ = ZoneInfo("Europe/Dublin")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt(hour: int = 10, minute: int = 0, days_ahead: int = 0) -> datetime:
    base = datetime(2026, 5, 18, hour, minute, tzinfo=TZ)
    return base + timedelta(days=days_ahead)


def _make_assignment(
    id: str = "a1",
    title: str = "Test Assignment",
    hours_ahead: float = 48.0,
    status: str = "todo",
    priority: int = 3,
    module_id: str | None = None,
) -> SimpleNamespace:
    now = _dt()
    due_at = now + timedelta(hours=hours_ahead)
    return SimpleNamespace(
        id=id,
        title=title,
        due_at=due_at,
        status=AssignmentStatus(status),
        priority=priority,
        module_id=module_id,
        estimated_hours=None,
        completed_hours=0,
    )


def _make_service(assignments: list, modules: list | None = None, next_block=None) -> NotificationService:
    """Return a NotificationService with a stubbed AcademicService."""

    service = object.__new__(NotificationService)
    service.timezone = TZ

    academic = MagicMock()
    academic.list_upcoming_assignments.return_value = assignments
    academic.list_modules.return_value = modules or []
    academic.get_next_study_recommendation.return_value = next_block
    academic.get_week_overview.return_value = SimpleNamespace(open_deadline_count=2)

    service._academic = academic
    return service


# ---------------------------------------------------------------------------
# DeadlineAlert model
# ---------------------------------------------------------------------------


def test_deadline_alert_format_hours_only() -> None:
    alert = DeadlineAlert(
        assignment_id="a1",
        title="NLP Essay",
        due_at=_dt(),
        hours_remaining=10.0,
        priority=4,
    )
    msg = alert.format_message()
    assert "NLP Essay" in msg
    assert "10h" in msg
    assert "high" in msg


def test_deadline_alert_format_days_and_hours() -> None:
    alert = DeadlineAlert(
        assignment_id="a1",
        title="Lab Report",
        due_at=_dt(),
        hours_remaining=49.0,
        priority=3,
        module_name="Biology",
    )
    msg = alert.format_message()
    assert "2d 1h" in msg
    assert "[Biology]" in msg


def test_deadline_alert_format_exact_days() -> None:
    alert = DeadlineAlert(
        assignment_id="a1",
        title="Project",
        due_at=_dt(),
        hours_remaining=48.0,
        priority=5,
    )
    msg = alert.format_message()
    assert "2d" in msg
    assert "critical" in msg


# ---------------------------------------------------------------------------
# OverdueAlert model
# ---------------------------------------------------------------------------


def test_overdue_alert_format_hours() -> None:
    alert = OverdueAlert(
        assignment_id="a2",
        title="Quiz 1",
        due_at=_dt(),
        hours_overdue=5.5,
    )
    msg = alert.format_message()
    assert "OVERDUE" in msg
    assert "5h" in msg
    assert "Quiz 1" in msg


def test_overdue_alert_format_days() -> None:
    alert = OverdueAlert(
        assignment_id="a2",
        title="Essay",
        due_at=_dt(),
        hours_overdue=50.0,
        module_name="English",
    )
    msg = alert.format_message()
    assert "2d 2h" in msg
    assert "[English]" in msg


# ---------------------------------------------------------------------------
# StudyBlockReminder model
# ---------------------------------------------------------------------------


def test_study_block_reminder_format() -> None:
    start = _dt(16, 30)
    reminder = StudyBlockReminder(
        assignment_id="a3",
        assignment_title="Deep Learning",
        start_at=start,
        minutes=90,
        module_name="ML",
    )
    msg = reminder.format_message()
    assert "16:30" in msg
    assert "Deep Learning" in msg
    assert "90min" in msg
    assert "[ML]" in msg


# ---------------------------------------------------------------------------
# NotificationService.deadline_alerts
# ---------------------------------------------------------------------------


def test_deadline_alerts_returns_active_within_window() -> None:
    assignments = [_make_assignment(hours_ahead=24.0)]
    service = _make_service(assignments)
    alerts = service.deadline_alerts(now=_dt(), alert_hours=72)
    assert len(alerts) == 1
    assert alerts[0].title == "Test Assignment"


def test_deadline_alerts_excludes_submitted() -> None:
    assignments = [_make_assignment(hours_ahead=24.0, status="submitted")]
    service = _make_service(assignments)
    alerts = service.deadline_alerts(now=_dt(), alert_hours=72)
    assert alerts == []


def test_deadline_alerts_excludes_outside_window() -> None:
    assignments = [_make_assignment(hours_ahead=96.0)]
    service = _make_service(assignments)
    alerts = service.deadline_alerts(now=_dt(), alert_hours=72)
    assert alerts == []


def test_deadline_alerts_excludes_already_passed() -> None:
    assignments = [_make_assignment(hours_ahead=-1.0)]
    service = _make_service(assignments)
    alerts = service.deadline_alerts(now=_dt(), alert_hours=72)
    assert alerts == []


def test_deadline_alerts_sorted_by_hours_remaining() -> None:
    assignments = [
        _make_assignment(id="a2", title="B", hours_ahead=60.0),
        _make_assignment(id="a1", title="A", hours_ahead=12.0),
    ]
    service = _make_service(assignments)
    alerts = service.deadline_alerts(now=_dt(), alert_hours=72)
    assert [a.title for a in alerts] == ["A", "B"]


def test_deadline_alerts_includes_module_name() -> None:
    module = SimpleNamespace(id="m1", name="CompSci")
    assignments = [_make_assignment(module_id="m1")]
    service = _make_service(assignments, modules=[module])
    alerts = service.deadline_alerts(now=_dt(), alert_hours=72)
    assert alerts[0].module_name == "CompSci"


# ---------------------------------------------------------------------------
# NotificationService.overdue_alerts
# ---------------------------------------------------------------------------


def test_overdue_alerts_returns_past_deadline_active() -> None:
    assignments = [_make_assignment(hours_ahead=-10.0)]
    service = _make_service(assignments)
    alerts = service.overdue_alerts(now=_dt())
    assert len(alerts) == 1
    assert alerts[0].title == "Test Assignment"


def test_overdue_alerts_excludes_submitted() -> None:
    assignments = [_make_assignment(hours_ahead=-5.0, status="submitted")]
    service = _make_service(assignments)
    alerts = service.overdue_alerts(now=_dt())
    assert alerts == []


def test_overdue_alerts_excludes_future() -> None:
    assignments = [_make_assignment(hours_ahead=24.0)]
    service = _make_service(assignments)
    alerts = service.overdue_alerts(now=_dt())
    assert alerts == []


def test_overdue_alerts_sorted_most_overdue_first() -> None:
    assignments = [
        _make_assignment(id="a2", title="Recent", hours_ahead=-5.0),
        _make_assignment(id="a1", title="Old", hours_ahead=-50.0),
    ]
    service = _make_service(assignments)
    alerts = service.overdue_alerts(now=_dt())
    assert alerts[0].title == "Old"


# ---------------------------------------------------------------------------
# NotificationService.study_block_reminder
# ---------------------------------------------------------------------------


def test_study_block_reminder_within_window() -> None:
    now = _dt(16, 0)
    block = SimpleNamespace(
        assignment_id="a1",
        assignment_title="Linear Algebra",
        start_at=_dt(16, 20),
        end_at=_dt(17, 20),
        minutes=60,
        module_name="Maths",
    )
    service = _make_service([], next_block=block)
    reminder = service.study_block_reminder(now=now, lookahead_minutes=30, min_minutes_ahead=10)
    assert reminder is not None
    assert reminder.assignment_title == "Linear Algebra"


def test_study_block_reminder_too_far_ahead() -> None:
    now = _dt(14, 0)
    block = SimpleNamespace(
        assignment_id="a1",
        assignment_title="Linear Algebra",
        start_at=_dt(16, 30),
        end_at=_dt(17, 30),
        minutes=60,
        module_name=None,
    )
    service = _make_service([], next_block=block)
    reminder = service.study_block_reminder(now=now, lookahead_minutes=30, min_minutes_ahead=10)
    assert reminder is None


def test_study_block_reminder_too_soon() -> None:
    now = _dt(16, 25)
    block = SimpleNamespace(
        assignment_id="a1",
        assignment_title="Linear Algebra",
        start_at=_dt(16, 30),
        end_at=_dt(17, 30),
        minutes=60,
        module_name=None,
    )
    service = _make_service([], next_block=block)
    reminder = service.study_block_reminder(now=now, lookahead_minutes=30, min_minutes_ahead=10)
    assert reminder is None


def test_study_block_reminder_no_block() -> None:
    service = _make_service([], next_block=None)
    assert service.study_block_reminder(now=_dt()) is None


# ---------------------------------------------------------------------------
# NotificationService.weekly_review_message
# ---------------------------------------------------------------------------


def test_weekly_review_message_with_deadlines() -> None:
    service = _make_service([])
    msg = service.weekly_review_message(now=_dt())
    assert "2 deadline(s)" in msg
    assert "/week" in msg


def test_weekly_review_message_no_deadlines() -> None:
    service = _make_service([])
    service._academic.get_week_overview.return_value = SimpleNamespace(open_deadline_count=0)
    msg = service.weekly_review_message(now=_dt())
    assert "no deadlines" in msg
    assert "/week" in msg


# ---------------------------------------------------------------------------
# format helpers
# ---------------------------------------------------------------------------


def test_format_deadline_alerts_message_non_empty() -> None:
    assignments = [_make_assignment(hours_ahead=24.0)]
    service = _make_service(assignments)
    msg = service.format_deadline_alerts_message(now=_dt(), alert_hours=72)
    assert "Deadline alert" in msg
    assert "Test Assignment" in msg


def test_format_deadline_alerts_message_empty() -> None:
    service = _make_service([])
    msg = service.format_deadline_alerts_message(now=_dt(), alert_hours=72)
    assert msg == ""


def test_format_overdue_message_non_empty() -> None:
    assignments = [_make_assignment(hours_ahead=-5.0)]
    service = _make_service(assignments)
    msg = service.format_overdue_message(now=_dt())
    assert "Overdue" in msg


def test_format_overdue_message_empty() -> None:
    service = _make_service([])
    msg = service.format_overdue_message(now=_dt())
    assert msg == ""


# ---------------------------------------------------------------------------
# seconds_until / seconds_until_weekday helpers
# ---------------------------------------------------------------------------


def test_seconds_until_future_same_day() -> None:
    now = datetime(2026, 5, 18, 7, 0, tzinfo=TZ)
    secs = seconds_until(8, 0, now)
    assert abs(secs - 3600) < 5


def test_seconds_until_already_passed_wraps_to_tomorrow() -> None:
    now = datetime(2026, 5, 18, 9, 0, tzinfo=TZ)
    secs = seconds_until(8, 0, now)
    assert secs > 80000  # ~23h


def test_seconds_until_weekday_sunday() -> None:
    # 2026-05-18 is a Monday; next Sunday is 2026-05-24
    now = datetime(2026, 5, 18, 10, 0, tzinfo=TZ)
    secs = seconds_until_weekday(6, 18, 0, now)
    assert secs > 0
    assert secs < 7 * 24 * 3600  # within one week
