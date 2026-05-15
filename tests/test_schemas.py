"""Tests for canonical Pydantic schemas."""

import pytest
from pydantic import ValidationError

from core.schemas import (
    ActionProposal,
    DailyPlanGenerated,
    FatigueLevel,
    MemoryItemExtracted,
    WorkShiftsExtracted,
)


def test_work_shifts_extracted_validates_correct_input() -> None:
    """WorkShiftsExtracted should accept the corrected array wrapper."""

    model = WorkShiftsExtracted(
        shifts=[
            {
                "workplace": "The Anchor",
                "date": "2026-05-18",
                "start_time": "18:00",
                "end_time": "23:30",
                "role": None,
                "commute_minutes": 25,
                "fatigue_level": "high",
                "notes": None,
                "confidence": 0.92,
            }
        ],
        needs_confirmation=False,
    )

    assert model.shifts[0].fatigue_level == FatigueLevel.HIGH


def test_work_shifts_extracted_rejects_missing_shifts_field() -> None:
    """WorkShiftsExtracted should require the top-level shifts array."""

    with pytest.raises(ValidationError):
        WorkShiftsExtracted(needs_confirmation=False)


def test_memory_item_extracted_validates_should_store_false() -> None:
    """MemoryItemExtracted should allow the model to decline noisy input."""

    model = MemoryItemExtracted(
        should_store=False,
        domain="studies",
        topic="small talk",
        summary="Message did not contain useful long-term memory.",
        importance="low",
        tags=[],
        confidence=0.8,
    )

    assert model.should_store is False


def test_daily_plan_generated_validates_capacity_warnings_and_reason() -> None:
    """DailyPlanGenerated should include capacity, warnings, and block reasons."""

    model = DailyPlanGenerated(
        date="2026-05-19",
        capacity="medium",
        blocks=[
            {
                "start_time": "10:00",
                "end_time": "12:00",
                "title": "Write literature review",
                "task_type": "writing",
                "intensity": "deep",
                "reason": "Deadline is soon and morning capacity is available.",
            }
        ],
        warnings=["Keep evening light after work."],
    )

    assert model.capacity == "medium"
    assert model.blocks[0].reason


def test_action_proposal_validates_correctly() -> None:
    """ActionProposal should validate a normal action wrapper."""

    proposal = ActionProposal(
        action_type="write_memory",
        payload={"summary": "A useful item"},
        confidence=0.88,
        requires_confirmation=False,
        reason="Store user-provided memory.",
    )

    assert proposal.action_type == "write_memory"


def test_fatigue_level_rejects_invalid_values() -> None:
    """FatigueLevel should only allow low, medium, or high."""

    with pytest.raises(ValueError):
        FatigueLevel("extreme")

