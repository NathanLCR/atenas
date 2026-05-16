"""Tests for Phase 5 Telegram data commands."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.bot import (
    AllowlistFilter,
    add_assignment_command,
    add_class_command,
    add_module_command,
    add_shift_command,
    assignments_command,
    classes_command,
    modules_command,
    set_hours_command,
    set_status_command,
    shifts_command,
)
from core.academic.models import (
    Assignment,
    AssignmentStatus,
    ClassSession,
    StudyModule,
    WorkShift,
)

TZ = ZoneInfo("Europe/Dublin")


@pytest.mark.asyncio
async def test_add_module_command_creates_module() -> None:
    update = _make_update(123, '/add_module name="Deep Learning" code="DL"')
    with patch("app.bot.AcademicService", return_value=_fake_service_with_module()):
        await _dispatch_if_allowed(update, add_module_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Module added" in reply
    assert "Deep Learning" in reply


@pytest.mark.asyncio
async def test_add_module_command_missing_name() -> None:
    update = _make_update(123, "/add_module")
    await _dispatch_if_allowed(update, add_module_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_add_class_command_creates_session() -> None:
    update = _make_update(123, '/add_class title="DL" day=mon start=10:00 end=12:00')
    with patch("app.bot.AcademicService", return_value=_fake_service_with_class()):
        await _dispatch_if_allowed(update, add_class_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Class added" in reply


@pytest.mark.asyncio
async def test_add_class_command_invalid_weekday() -> None:
    update = _make_update(123, '/add_class title="DL" day=xyz start=10:00 end=12:00')
    await _dispatch_if_allowed(update, add_class_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Invalid weekday" in reply


@pytest.mark.asyncio
async def test_add_class_command_missing_args() -> None:
    update = _make_update(123, "/add_class")
    await _dispatch_if_allowed(update, add_class_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_add_shift_command_creates_shift() -> None:
    update = _make_update(123, '/add_shift start="2026-05-18 16:00" end="2026-05-18 23:00"')
    with patch("app.bot.AcademicService", return_value=_fake_service_with_shift()):
        await _dispatch_if_allowed(update, add_shift_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Work shift added" in reply


@pytest.mark.asyncio
async def test_add_shift_command_missing_args() -> None:
    update = _make_update(123, "/add_shift")
    await _dispatch_if_allowed(update, add_shift_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_add_assignment_command_creates_assignment() -> None:
    update = _make_update(123, '/add_assignment title="NLP CA1" due="2026-05-21 23:59"')
    with patch("app.bot.AcademicService", return_value=_fake_service_with_assignment()):
        await _dispatch_if_allowed(update, add_assignment_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Assignment added" in reply


@pytest.mark.asyncio
async def test_add_assignment_command_missing_args() -> None:
    update = _make_update(123, "/add_assignment")
    await _dispatch_if_allowed(update, add_assignment_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_set_status_command_updates_status() -> None:
    update = _make_update(123, "/set_status assignment=test-id status=in_progress")
    with patch("app.bot.AcademicService", return_value=_fake_service_with_status_update()):
        await _dispatch_if_allowed(update, set_status_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Assignment updated" in reply
    assert "in_progress" in reply


@pytest.mark.asyncio
async def test_set_status_command_missing_args() -> None:
    update = _make_update(123, "/set_status")
    await _dispatch_if_allowed(update, set_status_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_set_hours_command_updates_hours() -> None:
    update = _make_update(123, "/set_hours assignment=test-id completed=2.5")
    with patch("app.bot.AcademicService", return_value=_fake_service_with_hours_update()):
        await _dispatch_if_allowed(update, set_hours_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Progress updated" in reply
    assert "2.5h" in reply


@pytest.mark.asyncio
async def test_set_hours_command_invalid_number() -> None:
    update = _make_update(123, "/set_hours assignment=test-id completed=abc")
    await _dispatch_if_allowed(update, set_hours_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "must be a number" in reply


@pytest.mark.asyncio
async def test_modules_command_lists_modules() -> None:
    update = _make_update(123, "/modules")
    with patch("app.bot.AcademicService", return_value=_fake_service_with_modules()):
        await _dispatch_if_allowed(update, modules_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Modules" in reply
    assert "Deep Learning" in reply


@pytest.mark.asyncio
async def test_modules_command_empty() -> None:
    update = _make_update(123, "/modules")
    with patch("app.bot.AcademicService", return_value=_fake_service_empty()):
        await _dispatch_if_allowed(update, modules_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "No modules found" in reply


@pytest.mark.asyncio
async def test_classes_command_lists_classes() -> None:
    update = _make_update(123, "/classes")
    with patch("app.bot.AcademicService", return_value=_fake_service_with_classes()):
        await _dispatch_if_allowed(update, classes_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Classes" in reply


@pytest.mark.asyncio
async def test_shifts_command_lists_shifts() -> None:
    update = _make_update(123, "/shifts")
    with patch("app.bot.AcademicService", return_value=_fake_service_with_shifts()):
        await _dispatch_if_allowed(update, shifts_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Work shifts" in reply


@pytest.mark.asyncio
async def test_assignments_command_lists_assignments() -> None:
    update = _make_update(123, "/assignments")
    with patch("app.bot.AcademicService", return_value=_fake_service_with_assignments()):
        await _dispatch_if_allowed(update, assignments_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Assignments" in reply
    assert "NLP CA1" in reply


@pytest.mark.asyncio
async def test_data_commands_respect_allowlist() -> None:
    update = _make_update(404, "/modules")
    if AllowlistFilter(allowed_user_ids=[123]).filter(update):
        await modules_command(update, _make_context())

    update.effective_message.reply_text.assert_not_called()


class _FakeDataService:
    def __init__(self, **kwargs) -> None:
        self._modules = kwargs.get("modules", [])
        self._classes = kwargs.get("classes", [])
        self._shifts = kwargs.get("shifts", [])
        self._assignments = kwargs.get("assignments", [])
        self._module_result = kwargs.get("module_result")
        self._class_result = kwargs.get("class_result")
        self._shift_result = kwargs.get("shift_result")
        self._assignment_result = kwargs.get("assignment_result")
        self._status_result = kwargs.get("status_result")
        self._hours_result = kwargs.get("hours_result")

    def add_module(self, **kwargs) -> object:
        return self._module_result or _cmd_result(False, "Module name is required.")

    def add_class_session(self, **kwargs) -> object:
        return self._class_result or _cmd_result(False, "Invalid weekday.")

    def add_work_shift(self, **kwargs) -> object:
        return self._shift_result or _cmd_result(False, "Invalid datetime.")

    def add_assignment(self, **kwargs) -> object:
        return self._assignment_result or _cmd_result(False, "Title is required.")

    def update_assignment_status(self, assignment_id: str, status: str) -> object:
        return self._status_result or _cmd_result(False, "Not found.")

    def update_completed_hours(self, assignment_id: str, hours: float) -> object:
        return self._hours_result or _cmd_result(False, "Not found.")

    def list_modules(self) -> list:
        return self._modules

    def list_class_sessions(self) -> list:
        return self._classes

    def list_all_work_shifts(self, limit: int = 50) -> list:
        return self._shifts[:limit]

    def list_all_assignments(self, include_completed: bool = True) -> list:
        return self._assignments


def _fake_service_with_module() -> _FakeDataService:
    return _FakeDataService(
        module_result=_cmd_result(True, "Module added\n\n#abc12345 — Deep Learning", "abc12345"),
    )


def _fake_service_with_class() -> _FakeDataService:
    return _FakeDataService(
        class_result=_cmd_result(True, "Class added\n\nDL\nMonday 10:00–12:00"),
    )


def _fake_service_with_shift() -> _FakeDataService:
    return _FakeDataService(
        shift_result=_cmd_result(True, "Work shift added\n\nMon 18 May\n16:00–23:00"),
    )


def _fake_service_with_assignment() -> _FakeDataService:
    return _FakeDataService(
        assignment_result=_cmd_result(True, "Assignment added\n\n#abc12345 — NLP CA1\nDue: Wed 21 May 23:59\nPriority: 3"),
    )


def _fake_service_with_status_update() -> _FakeDataService:
    return _FakeDataService(
        status_result=_cmd_result(True, "Assignment updated\n\n#test-id — Test\nStatus: in_progress"),
    )


def _fake_service_with_hours_update() -> _FakeDataService:
    return _FakeDataService(
        hours_result=_cmd_result(True, "Progress updated\n\n#test-id — Test\nCompleted: 2.5h\nRemaining: 3.5h"),
    )


def _fake_service_with_modules() -> _FakeDataService:
    return _FakeDataService(
        modules=[
            StudyModule(id="abc12345-def6", name="Deep Learning", code="DL"),
            StudyModule(id="xyz98765-abc1", name="NLP", code="NLP"),
        ]
    )


def _fake_service_with_classes() -> _FakeDataService:
    return _FakeDataService(
        classes=[
            ClassSession(id="a", title="DL", weekday=0, start_time="10:00", end_time="12:00"),
        ]
    )


def _fake_service_with_shifts() -> _FakeDataService:
    return _FakeDataService(
        shifts=[
            WorkShift(
                id="a", title="Work",
                start_at=datetime(2026, 5, 18, 16, 0, tzinfo=TZ),
                end_at=datetime(2026, 5, 18, 23, 0, tzinfo=TZ),
            ),
        ]
    )


def _fake_service_with_assignments() -> _FakeDataService:
    return _FakeDataService(
        assignments=[
            Assignment(
                id="abc12345-def6", title="NLP CA1",
                due_at=datetime(2026, 5, 21, 23, 59, tzinfo=TZ),
                status=AssignmentStatus.TODO,
                priority=2,
                estimated_hours=6,
            ),
        ]
    )


def _fake_service_empty() -> _FakeDataService:
    return _FakeDataService()


def _cmd_result(success: bool, message: str, record_id: str | None = None) -> SimpleNamespace:
    from dataclasses import dataclass, field

    @dataclass(frozen=True)
    class R:
        success: bool
        message: str
        record_id: str | None = None
        errors: list = field(default_factory=list)

    return R(success=success, message=message, record_id=record_id)


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
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        bot_data={"settings": _fake_settings()},
    )


def _fake_settings() -> SimpleNamespace:
    return SimpleNamespace(
        db_path="/tmp/test.sqlite",
        timezone="Europe/Dublin",
    )
