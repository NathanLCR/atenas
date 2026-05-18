"""Tests for Phase 4 Telegram planning commands."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.bot import AllowlistFilter, plan_command, study_command
from core.academic.planner import (
    PlannedStudyBlock,
    StudyPlan,
    StudyPlanSummary,
    UnscheduledWorkload,
)

TZ = ZoneInfo("Europe/Dublin")
MONDAY = date(2026, 5, 18)
SUNDAY = date(2026, 5, 24)


@pytest.mark.asyncio
async def test_plan_command_returns_weekly_plan() -> None:
    block = _block()
    plan = _study_plan(blocks=[block])
    with patch("app.bot.AcademicService", return_value=_FakePlanningService(plan)):
        update = _make_update(123, "/plan")
        await _dispatch_if_allowed(update, plan_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Study plan - 18 May to 24 May" in reply
    assert "Summary" in reply
    assert "NLP CA1" in reply
    assert "Planned: 2h00" in reply


@pytest.mark.asyncio
async def test_study_command_returns_next_block() -> None:
    block = _block()
    plan = _study_plan(blocks=[block])
    with patch("app.bot.AcademicService", return_value=_FakePlanningService(plan, today_block=block, next_block=block)):
        update = _make_update(123, "/study")
        await _dispatch_if_allowed(update, study_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Study next" in reply
    assert "NLP CA1" in reply
    assert "Reason: due soon" in reply
    assert "Priority: 2" in reply


@pytest.mark.asyncio
async def test_plan_command_empty_state() -> None:
    plan = _study_plan(blocks=[], required=0, planned=0)
    with patch("app.bot.AcademicService", return_value=_FakePlanningService(plan)):
        update = _make_update(123, "/plan")
        await _dispatch_if_allowed(update, plan_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply == "No open assignments to plan."


@pytest.mark.asyncio
async def test_plan_command_no_availability_state() -> None:
    unscheduled = _unscheduled()
    plan = _study_plan(
        blocks=[],
        available=0,
        required=120,
        planned=0,
        unscheduled_minutes=120,
        unscheduled=[unscheduled],
    )
    with patch("app.bot.AcademicService", return_value=_FakePlanningService(plan)):
        update = _make_update(123, "/plan")
        await _dispatch_if_allowed(update, plan_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "No study windows available this week." in reply
    assert "Required workload: 2h00" in reply
    assert "Unscheduled: 2h00" in reply


@pytest.mark.asyncio
async def test_planning_commands_include_warnings() -> None:
    plan = _study_plan(
        blocks=[],
        required=0,
        planned=0,
        unestimated=["Needs estimate"],
    )
    with patch("app.bot.AcademicService", return_value=_FakePlanningService(plan)):
        update = _make_update(123, "/study")
        await _dispatch_if_allowed(update, study_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "No study recommendation available." in reply
    assert "assignments need estimated hours" in reply


def _study_plan(
    *,
    blocks: list[PlannedStudyBlock],
    available: int = 240,
    required: int = 120,
    planned: int = 120,
    unscheduled_minutes: int = 0,
    unscheduled: list[UnscheduledWorkload] | None = None,
    unestimated: list[str] | None = None,
) -> StudyPlan:
    return StudyPlan(
        start_date=MONDAY,
        end_date=SUNDAY,
        blocks=blocks,
        unscheduled=unscheduled or [],
        summary=StudyPlanSummary(
            total_available_minutes=available,
            total_required_minutes=required,
            total_planned_minutes=planned,
            total_unscheduled_minutes=unscheduled_minutes,
            unestimated_assignments=unestimated or [],
            overdue_assignments=[],
        ),
    )


def _block() -> PlannedStudyBlock:
    return PlannedStudyBlock(
        assignment_id="a",
        assignment_title="NLP CA1",
        module_name="Natural Language Processing",
        start_at=datetime(2026, 5, 18, 14, 0, tzinfo=TZ),
        end_at=datetime(2026, 5, 18, 16, 0, tzinfo=TZ),
        minutes=120,
        due_at=datetime(2026, 5, 20, 17, 0, tzinfo=TZ),
        priority=2,
        reason="due soon",
    )


def _unscheduled() -> UnscheduledWorkload:
    return UnscheduledWorkload(
        assignment_id="a",
        assignment_title="NLP CA1",
        module_name=None,
        due_at=datetime(2026, 5, 20, 17, 0, tzinfo=TZ),
        priority=2,
        required_minutes=120,
        planned_minutes=0,
        unscheduled_minutes=120,
        reason="insufficient availability before deadline",
    )


class _FakePlanningService:
    def __init__(
        self,
        plan: StudyPlan,
        today_block: PlannedStudyBlock | None = None,
        next_block: PlannedStudyBlock | None = None,
    ) -> None:
        self.plan = plan
        self.today_block = today_block
        self.next_block = next_block

    def get_study_plan(self) -> StudyPlan:
        return self.plan

    def get_today_study_recommendation(self) -> PlannedStudyBlock | None:
        return self.today_block

    def get_next_study_recommendation(self) -> PlannedStudyBlock | None:
        return self.next_block


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
