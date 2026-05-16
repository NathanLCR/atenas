"""Tests for Phase 3 read-only Telegram schedule commands."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.bot import (
    AllowlistFilter,
    availability_command,
    deadlines_command,
    today_command,
    week_command,
)
from core.academic.models import (
    Assignment,
    AssignmentStatus,
    DayAvailability,
    DaySummary,
    StudyWindow,
    TimeBlock,
    TodayOverview,
    WeekAvailability,
    WeekOverview,
)

TZ = ZoneInfo("Europe/Dublin")
MONDAY = date(2026, 5, 18)


@pytest.mark.asyncio
async def test_today_command_returns_compact_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = _fake_service(today=_today_overview())
    monkeypatch.setattr("app.bot.get_academic_service", lambda: fake_service)
    update = _make_update(123, "/today")

    await _dispatch_if_allowed(update, today_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Today - Mon 18 May" in reply
    assert "Morning Lecture" in reply
    assert "Evening Shift" in reply
    assert "Demo Deadline" in reply
    assert "Total study time: 9h00" in reply


@pytest.mark.asyncio
async def test_week_command_returns_compact_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = _fake_service(week=_week_overview())
    monkeypatch.setattr("app.bot.get_academic_service", lambda: fake_service)
    update = _make_update(123, "/week")

    await _dispatch_if_allowed(update, week_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Week - 18 May to 24 May" in reply
    assert "- Classes: 1" in reply
    assert "Mon: classes 2h00, work 3h00, study 9h00" in reply


@pytest.mark.asyncio
async def test_deadlines_command_returns_sorted_deadlines(monkeypatch: pytest.MonkeyPatch) -> None:
    assignments = [
        _assignment("First Deadline", datetime(2026, 5, 21, 17, 0, tzinfo=TZ), priority=1),
        _assignment("Second Deadline", datetime(2026, 5, 25, 17, 0, tzinfo=TZ), priority=3),
    ]
    fake_service = _fake_service(assignments=assignments)
    monkeypatch.setattr("app.bot.get_academic_service", lambda: fake_service)
    update = _make_update(123, "/deadlines")

    await _dispatch_if_allowed(update, deadlines_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply.index("First Deadline") < reply.index("Second Deadline")
    assert "Priority: 1 | Status: todo" in reply


@pytest.mark.asyncio
async def test_availability_command_returns_today_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = _fake_service(today=_today_overview())
    monkeypatch.setattr("app.bot.get_academic_service", lambda: fake_service)
    update = _make_update(123, "/availability")

    await _dispatch_if_allowed(update, availability_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Availability today" in reply
    assert "08:00-10:00 - 2h00" in reply
    assert "Total: 9h00" in reply


@pytest.mark.asyncio
async def test_schedule_commands_respect_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = _fake_service(today=_today_overview())
    monkeypatch.setattr("app.bot.get_academic_service", lambda: fake_service)
    update = _make_update(404, "/today")

    if AllowlistFilter(allowed_user_ids=[123]).filter(update):
        await today_command(update, _make_context())

    update.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_today_command_empty_data_message_is_friendly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = _fake_service(today=_today_overview(empty=True))
    monkeypatch.setattr("app.bot.get_academic_service", lambda: fake_service)
    update = _make_update(123, "/today")

    await _dispatch_if_allowed(update, today_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "No classes, work shifts, or deadlines found." in reply
    assert "Available study time: 14h00" in reply


def _today_overview(empty: bool = False) -> TodayOverview:
    if empty:
        availability = DayAvailability(
            date=MONDAY,
            blocked=[],
            study_windows=[
                StudyWindow(
                    start_at=datetime(2026, 5, 18, 8, 0, tzinfo=TZ),
                    end_at=datetime(2026, 5, 18, 22, 0, tzinfo=TZ),
                    minutes=14 * 60,
                )
            ],
            total_study_minutes=14 * 60,
        )
        return TodayOverview(date=MONDAY, classes=[], work_shifts=[], deadlines=[], availability=availability)

    classes = [
        TimeBlock(
            title="Morning Lecture",
            start_at=datetime(2026, 5, 18, 10, 0, tzinfo=TZ),
            end_at=datetime(2026, 5, 18, 12, 0, tzinfo=TZ),
            kind="class",
        )
    ]
    work = [
        TimeBlock(
            title="Evening Shift",
            start_at=datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
            end_at=datetime(2026, 5, 18, 21, 0, tzinfo=TZ),
            kind="work",
        )
    ]
    windows = [
        StudyWindow(
            start_at=datetime(2026, 5, 18, 8, 0, tzinfo=TZ),
            end_at=datetime(2026, 5, 18, 10, 0, tzinfo=TZ),
            minutes=120,
        ),
        StudyWindow(
            start_at=datetime(2026, 5, 18, 12, 0, tzinfo=TZ),
            end_at=datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
            minutes=360,
        ),
        StudyWindow(
            start_at=datetime(2026, 5, 18, 21, 0, tzinfo=TZ),
            end_at=datetime(2026, 5, 18, 22, 0, tzinfo=TZ),
            minutes=60,
        ),
    ]
    availability = DayAvailability(
        date=MONDAY,
        blocked=classes + work,
        study_windows=windows,
        total_study_minutes=9 * 60,
    )
    return TodayOverview(
        date=MONDAY,
        classes=classes,
        work_shifts=work,
        deadlines=[_assignment("Demo Deadline", datetime(2026, 5, 21, 17, 0, tzinfo=TZ), priority=2)],
        availability=availability,
    )


def _week_overview() -> WeekOverview:
    day = _today_overview().availability
    availability = WeekAvailability(
        start_date=MONDAY,
        end_date=date(2026, 5, 24),
        days=[day],
        total_study_minutes=day.total_study_minutes,
    )
    return WeekOverview(
        start_date=MONDAY,
        end_date=date(2026, 5, 24),
        class_count=1,
        work_shift_count=1,
        open_deadline_count=1,
        availability=availability,
        day_summaries=[
            DaySummary(
                date=MONDAY,
                class_minutes=120,
                work_minutes=180,
                study_minutes=day.total_study_minutes,
            )
        ],
    )


def _assignment(title: str, due_at: datetime, priority: int) -> Assignment:
    return Assignment(
        title=title,
        due_at=due_at,
        status=AssignmentStatus.TODO,
        priority=priority,
    )


class _FakeService:
    def __init__(
        self,
        today: TodayOverview | None = None,
        week: WeekOverview | None = None,
        assignments: list[Assignment] | None = None,
    ) -> None:
        self.today = today or _today_overview()
        self.week = week or _week_overview()
        self.assignments = assignments or self.today.deadlines

    def get_today_overview(self) -> TodayOverview:
        return self.today

    def get_week_overview(self) -> WeekOverview:
        return self.week

    def list_upcoming_assignments(self, limit: int = 10) -> list[Assignment]:
        return self.assignments[:limit]


def _fake_service(
    today: TodayOverview | None = None,
    week: WeekOverview | None = None,
    assignments: list[Assignment] | None = None,
) -> _FakeService:
    return _FakeService(today=today, week=week, assignments=assignments)


async def _dispatch_if_allowed(update: SimpleNamespace, callback: object) -> None:
    if AllowlistFilter(allowed_user_ids=[update.effective_user.id]).filter(update):
        await callback(update, _make_context())


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_context() -> SimpleNamespace:
    return SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
