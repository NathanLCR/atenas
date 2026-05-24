"""Deterministic study planning for assignment workload."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Mapping, Sequence

from core.academic.models import Assignment, AssignmentStatus, WeekAvailability

INCLUDED_STATUSES = {
    AssignmentStatus.TODO.value,
    AssignmentStatus.IN_PROGRESS.value,
}
EXCLUDED_STATUSES = {
    AssignmentStatus.SUBMITTED.value,
    AssignmentStatus.DONE.value,
    AssignmentStatus.CANCELLED.value,
}
FINAL_SHORT_BLOCK_MINUTES = 20


@dataclass(frozen=True)
class PlanningSettings:
    """Configurable deterministic planning settings."""

    horizon_days: int = 7
    min_block_minutes: int = 45
    max_block_minutes: int = 120
    break_between_blocks_minutes: int = 15
    include_assignments_due_within_days: int = 30


@dataclass(frozen=True)
class AssignmentWorkload:
    """Open assignment workload after progress is applied."""

    assignment_id: str
    title: str
    module_name: str | None
    due_at: datetime
    priority: int
    estimated_minutes: int
    completed_minutes: int
    remaining_minutes: int
    status: str


@dataclass(frozen=True)
class PlannedStudyBlock:
    """A planned block of study time for one assignment."""

    assignment_id: str
    assignment_title: str
    module_name: str | None
    start_at: datetime
    end_at: datetime
    minutes: int
    due_at: datetime
    priority: int
    reason: str
    intensity: str = "medium"


@dataclass(frozen=True)
class UnscheduledWorkload:
    """Assignment workload that could not be placed before its deadline."""

    assignment_id: str
    assignment_title: str
    module_name: str | None
    due_at: datetime
    priority: int
    required_minutes: int
    planned_minutes: int
    unscheduled_minutes: int
    reason: str


@dataclass(frozen=True)
class StudyPlanSummary:
    """Aggregate capacity and warning information for a study plan."""

    total_available_minutes: int
    total_required_minutes: int
    total_planned_minutes: int
    total_unscheduled_minutes: int
    unestimated_assignments: list[str]
    overdue_assignments: list[str]


@dataclass(frozen=True)
class StudyPlan:
    """Deterministic plan for a date range."""

    start_date: date
    end_date: date
    blocks: list[PlannedStudyBlock]
    unscheduled: list[UnscheduledWorkload]
    summary: StudyPlanSummary


@dataclass
class _PlanningWindow:
    start_at: datetime
    end_at: datetime
    max_intensity: str = "deep"


def build_study_plan(
    *,
    assignments: Sequence[Assignment],
    availability: WeekAvailability,
    module_names_by_id: Mapping[str, str] | None,
    now: datetime,
    settings: PlanningSettings | None = None,
) -> StudyPlan:
    """Allocate open assignment workload into available study windows."""

    planning_settings = settings or PlanningSettings()
    module_names = module_names_by_id or {}
    workloads, unestimated, overdue = _assignment_workloads(
        assignments=assignments,
        module_names_by_id=module_names,
        now=now,
        settings=planning_settings,
    )
    workloads.sort(
        key=lambda item: (
            item.due_at,
            item.priority,
            -item.remaining_minutes,
            item.assignment_id,
        )
    )

    windows = [
        _PlanningWindow(start_at=window.start_at, end_at=window.end_at, max_intensity=getattr(window, "max_intensity", "deep"))
        for day in availability.days
        for window in day.study_windows
    ]
    windows.sort(key=lambda window: (window.start_at, window.end_at))

    blocks: list[PlannedStudyBlock] = []
    unscheduled: list[UnscheduledWorkload] = []
    for workload in workloads:
        planned_minutes = _allocate_workload(
            workload=workload,
            windows=windows,
            blocks=blocks,
            now=now,
            settings=planning_settings,
        )
        if planned_minutes < workload.remaining_minutes:
            unscheduled.append(
                UnscheduledWorkload(
                    assignment_id=workload.assignment_id,
                    assignment_title=workload.title,
                    module_name=workload.module_name,
                    due_at=workload.due_at,
                    priority=workload.priority,
                    required_minutes=workload.remaining_minutes,
                    planned_minutes=planned_minutes,
                    unscheduled_minutes=workload.remaining_minutes - planned_minutes,
                    reason="insufficient availability before deadline",
                )
            )

    planned_total = sum(block.minutes for block in blocks)
    unscheduled_total = sum(item.unscheduled_minutes for item in unscheduled)
    summary = StudyPlanSummary(
        total_available_minutes=availability.total_study_minutes,
        total_required_minutes=sum(workload.remaining_minutes for workload in workloads),
        total_planned_minutes=planned_total,
        total_unscheduled_minutes=unscheduled_total,
        unestimated_assignments=unestimated,
        overdue_assignments=overdue,
    )
    return StudyPlan(
        start_date=availability.start_date,
        end_date=availability.end_date,
        blocks=blocks,
        unscheduled=unscheduled,
        summary=summary,
    )


def next_study_block(plan: StudyPlan, now: datetime) -> PlannedStudyBlock | None:
    """Return the next planned block at or after now."""

    future_blocks = [block for block in plan.blocks if block.end_at > now]
    if not future_blocks:
        return None
    return sorted(future_blocks, key=lambda block: (block.start_at, block.assignment_id))[0]


def today_study_block(plan: StudyPlan, now: datetime) -> PlannedStudyBlock | None:
    """Return the next planned block for today, if one exists."""

    today = now.date()
    future_today = [
        block
        for block in plan.blocks
        if block.end_at > now and block.start_at.date() == today
    ]
    if not future_today:
        return None
    return sorted(future_today, key=lambda block: (block.start_at, block.assignment_id))[0]


def _assignment_workloads(
    *,
    assignments: Sequence[Assignment],
    module_names_by_id: Mapping[str, str],
    now: datetime,
    settings: PlanningSettings,
) -> tuple[list[AssignmentWorkload], list[str], list[str]]:
    include_until = now + timedelta(days=settings.include_assignments_due_within_days)
    workloads: list[AssignmentWorkload] = []
    unestimated: list[str] = []
    overdue: list[str] = []

    for assignment in assignments:
        status = assignment.status.value
        if status in EXCLUDED_STATUSES or status not in INCLUDED_STATUSES:
            continue

        is_overdue = assignment.due_at < now
        if is_overdue:
            overdue.append(assignment.title)

        if assignment.estimated_hours is None:
            unestimated.append(assignment.title)
            continue

        if is_overdue or assignment.due_at > include_until:
            continue

        estimated_minutes = round(assignment.estimated_hours * 60)
        completed_minutes = round((assignment.completed_hours or 0) * 60)
        remaining_minutes = max(estimated_minutes - completed_minutes, 0)
        if remaining_minutes <= 0:
            continue

        module_name = (
            module_names_by_id.get(assignment.module_id)
            if assignment.module_id is not None
            else None
        )
        workloads.append(
            AssignmentWorkload(
                assignment_id=assignment.id,
                title=assignment.title,
                module_name=module_name,
                due_at=assignment.due_at,
                priority=assignment.priority,
                estimated_minutes=estimated_minutes,
                completed_minutes=completed_minutes,
                remaining_minutes=remaining_minutes,
                status=status,
            )
        )
    return workloads, unestimated, overdue


def _allocate_workload(
    *,
    workload: AssignmentWorkload,
    windows: list[_PlanningWindow],
    blocks: list[PlannedStudyBlock],
    now: datetime,
    settings: PlanningSettings,
) -> int:
    remaining_minutes = workload.remaining_minutes
    planned_minutes = 0

    for window in windows:
        if remaining_minutes <= 0:
            break
        if window.start_at >= workload.due_at:
            continue

        usable_end = min(window.end_at, workload.due_at)
        while remaining_minutes > 0 and window.start_at < usable_end:
            available_minutes = _duration_minutes(window.start_at, usable_end)
            duration = _block_duration(
                available_minutes=available_minutes,
                remaining_minutes=remaining_minutes,
                settings=settings,
            )
            if duration is None:
                break

            block_start = window.start_at
            block_end = block_start + timedelta(minutes=duration)
            blocks.append(
                PlannedStudyBlock(
                    assignment_id=workload.assignment_id,
                    assignment_title=workload.title,
                    module_name=workload.module_name,
                    start_at=block_start,
                    end_at=block_end,
                    minutes=duration,
                    due_at=workload.due_at,
                    priority=workload.priority,
                    reason=_planning_reason(workload, now),
                    intensity=_block_intensity(window),
                )
            )
            remaining_minutes -= duration
            planned_minutes += duration

            next_start = block_end
            if next_start < window.end_at:
                next_start = next_start + timedelta(
                    minutes=settings.break_between_blocks_minutes
                )
            window.start_at = min(next_start, window.end_at)

    return planned_minutes


def _block_duration(
    *,
    available_minutes: int,
    remaining_minutes: int,
    settings: PlanningSettings,
) -> int | None:
    if available_minutes <= 0:
        return None
    if available_minutes < settings.min_block_minutes:
        if remaining_minutes <= available_minutes and remaining_minutes >= FINAL_SHORT_BLOCK_MINUTES:
            return remaining_minutes
        return None

    duration = min(
        settings.max_block_minutes,
        remaining_minutes,
        available_minutes,
    )
    if duration >= settings.min_block_minutes:
        return duration
    if duration == remaining_minutes and duration >= FINAL_SHORT_BLOCK_MINUTES:
        return duration
    return None


def _planning_reason(workload: AssignmentWorkload, now: datetime) -> str:
    if workload.due_at <= now + timedelta(hours=48):
        return "due soon"
    if workload.priority <= 2:
        return "high priority"
    if workload.remaining_minutes >= 360:
        return "large workload"
    return "scheduled by deadline order"


def _duration_minutes(start_at: datetime, end_at: datetime) -> int:
    return int((end_at - start_at).total_seconds() // 60)


def _block_intensity(window: _PlanningWindow) -> str:
    cap = getattr(window, "max_intensity", "deep")
    if cap in {"recovery", "light", "medium", "deep"}:
        return cap
    return "medium"
