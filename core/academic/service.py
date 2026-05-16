"""Service layer for deterministic academic and work scheduling."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.availability import (
    DEFAULT_DAY_END,
    DEFAULT_DAY_START,
    DEFAULT_MINIMUM_STUDY_WINDOW_MINUTES,
    calculate_availability,
)
from core.academic.models import (
    Assignment,
    AssignmentStatus,
    ClassSession,
    DaySummary,
    StudyModule,
    TimeBlock,
    TodayOverview,
    WeekAvailability,
    WeekOverview,
    WorkShift,
)
from core.academic.planner import (
    PlannedStudyBlock,
    PlanningSettings,
    StudyPlan,
    StudyPlanSummary,
    build_study_plan,
    next_study_block,
    today_study_block,
)
from core.academic.repository import AcademicRepository
from core.time import (
    combine_local,
    ensure_local_datetime,
    parse_due_at,
    parse_hhmm,
    week_bounds,
)


class AcademicService:
    """Deterministic scheduling service used by Telegram and dashboard views."""

    def __init__(
        self,
        db_path: Path | str,
        timezone: str | ZoneInfo = "Europe/Dublin",
    ) -> None:
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
        self.repository = AcademicRepository(db_path, self.timezone)

    def create_module(
        self,
        name: str,
        code: str | None = None,
        lecturer: str | None = None,
        notes: str | None = None,
    ) -> StudyModule:
        """Create a study module."""

        return self.repository.create_module(
            StudyModule(code=code, name=name, lecturer=lecturer, notes=notes)
        )

    def list_modules(self) -> list[StudyModule]:
        """List study modules."""

        return self.repository.list_modules()

    def create_class_session(
        self,
        title: str,
        weekday: int,
        start_time: str,
        end_time: str,
        module_id: str | None = None,
        location: str | None = None,
        recurrence: str = "weekly",
        active: bool = True,
        notes: str | None = None,
    ) -> ClassSession:
        """Create a weekly class session."""

        return self.repository.create_class_session(
            ClassSession(
                module_id=module_id,
                title=title,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                location=location,
                recurrence=recurrence,
                active=active,
                notes=notes,
            )
        )

    def list_class_sessions(self, active_only: bool = True) -> list[ClassSession]:
        """List weekly class sessions."""

        return self.repository.list_class_sessions(active_only=active_only)

    def create_work_shift(
        self,
        title: str,
        start_at: str | datetime,
        end_at: str | datetime,
        location: str | None = None,
        role: str | None = None,
        energy_cost: int | None = None,
        notes: str | None = None,
    ) -> WorkShift:
        """Create a dated work shift."""

        start = ensure_local_datetime(
            datetime.fromisoformat(start_at) if isinstance(start_at, str) else start_at,
            self.timezone,
        )
        end = ensure_local_datetime(
            datetime.fromisoformat(end_at) if isinstance(end_at, str) else end_at,
            self.timezone,
        )
        return self.repository.create_work_shift(
            WorkShift(
                title=title,
                start_at=start,
                end_at=end,
                location=location,
                role=role,
                energy_cost=energy_cost,
                notes=notes,
            )
        )

    def list_work_shifts(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[WorkShift]:
        """List dated work shifts."""

        return self.repository.list_work_shifts(start_date=start_date, end_date=end_date)

    def create_assignment(
        self,
        title: str,
        due_at: str | datetime | date,
        module_id: str | None = None,
        status: AssignmentStatus | str = AssignmentStatus.TODO,
        priority: int = 3,
        weight: float | None = None,
        estimated_hours: float | None = None,
        completed_hours: float = 0,
        notes: str | None = None,
    ) -> Assignment:
        """Create an assignment or academic deadline."""

        parsed_due_at = parse_due_at(due_at, self.timezone)
        parsed_status = (
            status if isinstance(status, AssignmentStatus) else AssignmentStatus(status)
        )
        return self.repository.create_assignment(
            Assignment(
                module_id=module_id,
                title=title,
                due_at=parsed_due_at,
                status=parsed_status,
                priority=priority,
                weight=weight,
                estimated_hours=estimated_hours,
                completed_hours=completed_hours,
                notes=notes,
            )
        )

    def list_upcoming_assignments(
        self,
        limit: int = 10,
        include_completed: bool = False,
    ) -> list[Assignment]:
        """List upcoming assignments sorted by due date and priority."""

        return self.repository.list_upcoming_assignments(
            limit=limit,
            include_completed=include_completed,
        )

    def get_today_overview(self, now: datetime | None = None) -> TodayOverview:
        """Return today's classes, work, deadlines, and availability."""

        now_local = self._now(now)
        today = now_local.date()
        availability = self.get_availability(today, today, now=now_local).days[0]
        deadlines = [
            assignment
            for assignment in self.list_upcoming_assignments(limit=25)
            if today <= assignment.due_at.date() <= today + timedelta(days=7)
        ][:5]
        return TodayOverview(
            date=today,
            classes=self._class_blocks_for_day(today),
            work_shifts=self._work_blocks_for_day(today),
            deadlines=deadlines,
            availability=availability,
        )

    def get_week_overview(
        self,
        reference_date: date | None = None,
        now: datetime | None = None,
    ) -> WeekOverview:
        """Return a Monday-Sunday scheduling overview."""

        now_local = self._now(now)
        anchor = reference_date or now_local.date()
        start_date, end_date = week_bounds(anchor)
        availability = self.get_availability(start_date, end_date, now=now_local)
        class_sessions = self.list_class_sessions()
        work_shifts = self.list_work_shifts(start_date=start_date, end_date=end_date)
        deadlines_this_week = [
            assignment
            for assignment in self.list_upcoming_assignments(limit=100)
            if start_date <= assignment.due_at.date() <= end_date
        ]
        return WeekOverview(
            start_date=start_date,
            end_date=end_date,
            class_count=sum(1 for session in class_sessions if 0 <= session.weekday <= 6),
            work_shift_count=len(work_shifts),
            open_deadline_count=len(deadlines_this_week),
            availability=availability,
            day_summaries=[
                DaySummary(
                    date=day.date,
                    class_minutes=self._class_minutes_for_day(day.date),
                    work_minutes=self._work_minutes_for_day(day.date),
                    study_minutes=day.total_study_minutes,
                )
                for day in availability.days
            ],
        )

    def get_study_plan(
        self,
        reference_date: date | None = None,
        now: datetime | None = None,
        horizon_days: int = 7,
    ) -> StudyPlan:
        """Return a deterministic on-demand study plan."""

        if horizon_days < 1:
            raise ValueError("horizon_days must be at least 1")

        now_local = self._now(now)
        anchor = reference_date or now_local.date()
        start_date, _ = week_bounds(anchor)
        end_date = start_date + timedelta(days=horizon_days - 1)
        settings = PlanningSettings(horizon_days=horizon_days)
        availability = self.get_availability(
            start_date,
            end_date,
            now=now_local,
            minimum_study_window_minutes=settings.min_block_minutes,
        )
        module_names = {module.id: module.name for module in self.list_modules()}
        assignments = self.list_upcoming_assignments(limit=1000, include_completed=True)
        return build_study_plan(
            assignments=assignments,
            availability=availability,
            module_names_by_id=module_names,
            now=now_local,
            settings=settings,
        )

    def get_today_study_recommendation(
        self,
        now: datetime | None = None,
    ) -> PlannedStudyBlock | None:
        """Return the next planned study block today, if one exists."""

        now_local = self._now(now)
        return today_study_block(self.get_study_plan(now=now_local), now_local)

    def get_next_study_recommendation(
        self,
        now: datetime | None = None,
    ) -> PlannedStudyBlock | None:
        """Return the next planned study block in the current plan, if one exists."""

        now_local = self._now(now)
        return next_study_block(self.get_study_plan(now=now_local), now_local)

    def get_workload_summary(
        self,
        reference_date: date | None = None,
        now: datetime | None = None,
    ) -> StudyPlanSummary:
        """Return deterministic workload pressure for the planning range."""

        return self.get_study_plan(reference_date=reference_date, now=now).summary

    def get_availability(
        self,
        start_date: date,
        end_date: date,
        now: datetime | None = None,
        day_start: time = DEFAULT_DAY_START,
        day_end: time = DEFAULT_DAY_END,
        minimum_study_window_minutes: int = DEFAULT_MINIMUM_STUDY_WINDOW_MINUTES,
    ) -> WeekAvailability:
        """Calculate deterministic study availability for a date range."""

        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        return calculate_availability(
            start_date=start_date,
            end_date=end_date,
            class_sessions=self.list_class_sessions(),
            work_shifts=self.list_work_shifts(start_date=start_date, end_date=end_date),
            timezone=self.timezone,
            now=now,
            day_start=day_start,
            day_end=day_end,
            minimum_study_window_minutes=minimum_study_window_minutes,
        )

    def _now(self, now: datetime | None) -> datetime:
        if now is None:
            return datetime.now(self.timezone)
        return ensure_local_datetime(now, self.timezone)

    def _class_blocks_for_day(self, day: date) -> list[TimeBlock]:
        blocks: list[TimeBlock] = []
        for session in self.list_class_sessions():
            if not session.active or session.weekday != day.weekday():
                continue
            blocks.append(
                TimeBlock(
                    title=session.title,
                    start_at=combine_local(day, parse_hhmm(session.start_time), self.timezone),
                    end_at=combine_local(day, parse_hhmm(session.end_time), self.timezone),
                    kind="class",
                    metadata={"session_id": session.id, "module_id": session.module_id},
                )
            )
        return blocks

    def _work_blocks_for_day(self, day: date) -> list[TimeBlock]:
        blocks = []
        for shift in self.list_work_shifts(start_date=day, end_date=day):
            if shift.start_at.date() <= day <= shift.end_at.date():
                blocks.append(
                    TimeBlock(
                        title=shift.title,
                        start_at=shift.start_at,
                        end_at=shift.end_at,
                        kind="work",
                        metadata={"shift_id": shift.id, "role": shift.role},
                    )
                )
        return blocks

    def _class_minutes_for_day(self, day: date) -> int:
        return sum(
            _duration_minutes(block.start_at, block.end_at)
            for block in self._class_blocks_for_day(day)
        )

    def _work_minutes_for_day(self, day: date) -> int:
        day_start = combine_local(day, time.min, self.timezone)
        day_end = combine_local(day, time.max, self.timezone)
        total = 0
        for shift in self.list_work_shifts(start_date=day, end_date=day):
            start = max(shift.start_at, day_start)
            end = min(shift.end_at, day_end)
            if start < end:
                total += _duration_minutes(start, end)
        return total


def get_academic_service() -> AcademicService:
    """Build a service from process settings."""

    from app.config import get_settings

    settings = get_settings()
    return AcademicService(settings.db_path, timezone=settings.timezone)


def _duration_minutes(start_at: datetime, end_at: datetime) -> int:
    return int((end_at - start_at).total_seconds() // 60)
