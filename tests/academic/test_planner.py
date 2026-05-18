"""Deterministic study planner tests for Phase 4."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.models import (
    Assignment,
    AssignmentStatus,
    DayAvailability,
    StudyWindow,
    WeekAvailability,
)
from core.academic.planner import PlanningSettings, build_study_plan
from core.academic.service import AcademicService

TZ = ZoneInfo("Europe/Dublin")
MONDAY = date(2026, 5, 18)
NOW = datetime(2026, 5, 18, 8, 0, tzinfo=TZ)


def test_no_assignments_returns_empty_plan() -> None:
    plan = _plan(assignments=[])

    assert plan.blocks == []
    assert plan.summary.total_required_minutes == 0
    assert plan.summary.total_planned_minutes == 0


def test_assignment_without_estimated_hours_is_warned_not_scheduled() -> None:
    plan = _plan(
        assignments=[
            _assignment("Needs estimate", "a", estimated_hours=None),
        ]
    )

    assert plan.blocks == []
    assert plan.summary.unestimated_assignments == ["Needs estimate"]
    assert plan.summary.total_planned_minutes == 0


def test_completed_assignment_statuses_are_excluded() -> None:
    plan = _plan(
        assignments=[
            _assignment("Submitted", "a", status=AssignmentStatus.SUBMITTED),
            _assignment("Done", "b", status=AssignmentStatus.DONE),
            _assignment("Cancelled", "c", status=AssignmentStatus.CANCELLED),
        ]
    )

    assert plan.blocks == []
    assert plan.summary.total_required_minutes == 0


def test_todo_and_in_progress_assignments_are_included() -> None:
    plan = _plan(
        assignments=[
            _assignment("Todo", "a", status=AssignmentStatus.TODO),
            _assignment("In progress", "b", status=AssignmentStatus.IN_PROGRESS),
        ],
        windows=[_window("09:00", "13:00")],
    )

    titles = {block.assignment_title for block in plan.blocks}
    assert titles == {"Todo", "In progress"}


def test_completed_hours_reduce_remaining_workload() -> None:
    plan = _plan(
        assignments=[
            _assignment("Progress", "a", estimated_hours=5, completed_hours=2),
        ],
        windows=[_window("09:00", "15:00")],
    )

    assert plan.summary.total_required_minutes == 180
    assert plan.summary.total_planned_minutes == 180


def test_earliest_deadline_first_ordering() -> None:
    plan = _plan(
        assignments=[
            _assignment("Friday", "a", due_at=datetime(2026, 5, 22, 17, 0, tzinfo=TZ)),
            _assignment("Tuesday", "b", due_at=datetime(2026, 5, 19, 17, 0, tzinfo=TZ)),
        ],
        windows=[_window("09:00", "13:00")],
    )

    assert plan.blocks[0].assignment_title == "Tuesday"


def test_priority_tie_breaker() -> None:
    due_at = datetime(2026, 5, 21, 17, 0, tzinfo=TZ)
    plan = _plan(
        assignments=[
            _assignment("Normal", "a", due_at=due_at, priority=3),
            _assignment("High", "b", due_at=due_at, priority=1),
        ],
        windows=[_window("09:00", "13:00")],
    )

    assert plan.blocks[0].assignment_title == "High"


def test_workload_tie_breaker_prefers_larger_remaining_work() -> None:
    due_at = datetime(2026, 5, 21, 17, 0, tzinfo=TZ)
    plan = _plan(
        assignments=[
            _assignment("Small", "a", due_at=due_at, estimated_hours=2),
            _assignment("Large", "b", due_at=due_at, estimated_hours=5),
        ],
        windows=[_window("09:00", "18:00")],
    )

    assert plan.blocks[0].assignment_title == "Large"


def test_stable_id_tie_breaker() -> None:
    due_at = datetime(2026, 5, 21, 17, 0, tzinfo=TZ)
    plan = _plan(
        assignments=[
            _assignment("Second", "b", due_at=due_at),
            _assignment("First", "a", due_at=due_at),
        ],
        windows=[_window("09:00", "13:00")],
    )

    assert plan.blocks[0].assignment_title == "First"


def test_planner_does_not_schedule_after_deadline() -> None:
    due_at = datetime(2026, 5, 18, 12, 0, tzinfo=TZ)
    plan = _plan(
        assignments=[
            _assignment("Deadline", "a", due_at=due_at, estimated_hours=6),
        ],
        windows=[_window("09:00", "17:00")],
    )

    assert all(block.end_at <= due_at for block in plan.blocks)
    assert plan.unscheduled[0].assignment_title == "Deadline"
    assert plan.unscheduled[0].unscheduled_minutes > 0


def test_insufficient_capacity_warning_is_reported() -> None:
    plan = _plan(
        assignments=[
            _assignment("Too much", "a", estimated_hours=10),
        ],
        windows=[_window("09:00", "13:00")],
        settings=PlanningSettings(max_block_minutes=240, break_between_blocks_minutes=0),
    )

    assert plan.summary.total_planned_minutes == 240
    assert plan.summary.total_unscheduled_minutes == 360
    assert plan.unscheduled[0].reason == "insufficient availability before deadline"


def test_long_windows_are_split_with_breaks() -> None:
    plan = _plan(
        assignments=[
            _assignment("Long", "a", estimated_hours=4),
        ],
        windows=[_window("09:00", "13:00")],
    )

    assert all(block.minutes <= 120 for block in plan.blocks)
    assert plan.blocks[1].start_at == plan.blocks[0].end_at + timedelta(minutes=15)


def test_minimum_block_length_and_final_short_block_exception() -> None:
    too_short = _plan(
        assignments=[
            _assignment("Too short", "a", estimated_hours=1),
        ],
        windows=[_window("09:00", "09:30")],
    )
    final_short = _plan(
        assignments=[
            _assignment("Final short", "a", estimated_hours=0.5),
        ],
        windows=[_window("09:00", "09:30")],
    )

    assert too_short.blocks == []
    assert final_short.blocks[0].minutes == 30


def test_service_plan_excludes_past_time_today(tmp_db: Path) -> None:
    service = AcademicService(tmp_db)
    service.create_assignment(
        "Today plan",
        datetime(2026, 5, 19, 17, 0, tzinfo=TZ),
        estimated_hours=2,
    )

    plan = service.get_study_plan(
        reference_date=MONDAY,
        now=datetime(2026, 5, 18, 14, 0, tzinfo=TZ),
    )

    assert plan.blocks[0].start_at >= datetime(2026, 5, 18, 14, 0, tzinfo=TZ)


def test_overdue_assignment_is_warned_not_scheduled() -> None:
    plan = _plan(
        assignments=[
            _assignment(
                "Overdue",
                "a",
                due_at=datetime(2026, 5, 18, 7, 0, tzinfo=TZ),
                estimated_hours=1,
            ),
        ]
    )

    assert plan.blocks == []
    assert plan.summary.overdue_assignments == ["Overdue"]


def test_planning_output_is_deterministic() -> None:
    assignments = [
        _assignment("A", "a", estimated_hours=2),
        _assignment("B", "b", estimated_hours=2, priority=2),
    ]
    windows = [_window("09:00", "14:00")]

    first = _plan(assignments=assignments, windows=windows)
    second = _plan(assignments=assignments, windows=windows)

    assert first == second


def _plan(
    *,
    assignments: list[Assignment],
    windows: list[StudyWindow] | None = None,
    settings: PlanningSettings | None = None,
):
    return build_study_plan(
        assignments=assignments,
        availability=_availability(windows or [_window("09:00", "17:00")]),
        module_names_by_id={},
        now=NOW,
        settings=settings,
    )


def _assignment(
    title: str,
    assignment_id: str,
    *,
    due_at: datetime | None = None,
    status: AssignmentStatus = AssignmentStatus.TODO,
    priority: int = 3,
    estimated_hours: float | None = 1,
    completed_hours: float = 0,
) -> Assignment:
    return Assignment(
        id=assignment_id,
        title=title,
        due_at=due_at or datetime(2026, 5, 21, 17, 0, tzinfo=TZ),
        status=status,
        priority=priority,
        estimated_hours=estimated_hours,
        completed_hours=completed_hours,
    )


def _availability(windows: list[StudyWindow]) -> WeekAvailability:
    return WeekAvailability(
        start_date=MONDAY,
        end_date=MONDAY,
        days=[
            DayAvailability(
                date=MONDAY,
                blocked=[],
                study_windows=windows,
                total_study_minutes=sum(window.minutes for window in windows),
            )
        ],
        total_study_minutes=sum(window.minutes for window in windows),
    )


def _window(start: str, end: str) -> StudyWindow:
    start_at = datetime.fromisoformat(f"2026-05-18T{start}:00").replace(tzinfo=TZ)
    end_at = datetime.fromisoformat(f"2026-05-18T{end}:00").replace(tzinfo=TZ)
    return StudyWindow(
        start_at=start_at,
        end_at=end_at,
        minutes=int((end_at - start_at).total_seconds() // 60),
    )
