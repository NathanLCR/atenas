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
    DuplicateModuleGroup,
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
from core.academic.validators import (
    ALLOWED_STATUSES,
    CommandResult,
    parse_datetime_input,
    parse_datetime_strict,
    validate_energy_cost,
    validate_fatigue_level,
    validate_hours,
    validate_notes,
    validate_priority,
    validate_status,
    validate_text_field,
    validate_weight,
)
from core.time import (
    combine_local,
    ensure_local_datetime,
    parse_due_at,
    parse_hhmm,
    week_bounds,
)
from core.schemas import FatigueLevel


class AcademicService:
    """Deterministic scheduling service used by Telegram and dashboard views.

    Coordinates availability calculation, study planning, and CRUD operations
    for modules, classes, shifts, and assignments. All scheduling decisions
    are deterministic — no randomness or LLM involvement.
    """

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

    def detect_duplicate_modules(self) -> list[DuplicateModuleGroup]:
        """Return duplicate module groups using normalized name and code."""

        grouped: dict[tuple[str, str], list[StudyModule]] = {}
        for module in self.list_modules():
            key = (_normalize_module_label(module.name), _normalize_module_label(module.code or ""))
            grouped.setdefault(key, []).append(module)

        duplicates: list[DuplicateModuleGroup] = []
        for key, modules in grouped.items():
            if len(modules) < 2:
                continue
            ordered = sorted(modules, key=lambda item: (item.created_at, item.id))
            canonical = ordered[0]
            duplicates.append(
                DuplicateModuleGroup(
                    key="|".join(key),
                    canonical_module=canonical,
                    duplicate_modules=ordered[1:],
                    all_modules=ordered,
                )
            )
        return sorted(
            duplicates,
            key=lambda group: (group.canonical_module.name.casefold(), group.key),
        )

    def delete_modules(self, module_ids: list[str]) -> CommandResult:
        """Delete unreferenced modules after deterministic validation."""

        requested_ids = _unique_ids(module_ids)
        if not requested_ids:
            return CommandResult(success=False, message="No module IDs were provided.")

        modules_by_id = {module.id: module for module in self.list_modules()}
        missing = [module_id for module_id in requested_ids if module_id not in modules_by_id]
        if missing:
            return CommandResult(
                success=False,
                message=f"Module not found: {', '.join(missing)}",
            )

        reference_counts = self.repository.module_reference_counts(requested_ids)
        referenced = [
            modules_by_id[module_id]
            for module_id in requested_ids
            if reference_counts.get(module_id, 0) > 0
        ]
        if referenced:
            labels = ", ".join(f"#{module.id[:8]} {module.name}" for module in referenced)
            return CommandResult(
                success=False,
                message=f"Refusing to delete referenced modules. Use deduplication instead: {labels}",
            )

        deleted = self.repository.delete_modules(requested_ids)
        labels = "\n".join(
            f"- #{modules_by_id[module_id].id[:8]} {modules_by_id[module_id].name}"
            for module_id in requested_ids
        )
        return CommandResult(
            success=True,
            message=f"Deleted {deleted} module(s).\n\n{labels}",
        )

    def deduplicate_modules(
        self,
        groups: list[tuple[str, list[str]]],
    ) -> CommandResult:
        """Merge duplicate modules into canonical modules, then delete duplicates."""

        if not groups:
            return CommandResult(success=False, message="No duplicate module groups were provided.")

        modules_by_id = {module.id: module for module in self.list_modules()}
        deleted_modules: list[StudyModule] = []
        reassigned_counts: dict[str, int] = {}

        for canonical_id, duplicate_ids in groups:
            canonical = modules_by_id.get(canonical_id)
            if canonical is None:
                return CommandResult(success=False, message=f"Canonical module not found: {canonical_id}")

            dedupe_ids = _unique_ids(duplicate_ids)
            if canonical_id in dedupe_ids:
                return CommandResult(
                    success=False,
                    message="Canonical module cannot also be deleted.",
                )
            if not dedupe_ids:
                return CommandResult(success=False, message="No duplicate module IDs were provided.")

            canonical_key = _module_duplicate_key(canonical)
            for module_id in dedupe_ids:
                duplicate = modules_by_id.get(module_id)
                if duplicate is None:
                    return CommandResult(success=False, message=f"Duplicate module not found: {module_id}")
                if _module_duplicate_key(duplicate) != canonical_key:
                    return CommandResult(
                        success=False,
                        message=(
                            f"Module #{duplicate.id[:8]} {duplicate.name} is not a duplicate "
                            f"of #{canonical.id[:8]} {canonical.name}."
                        ),
                    )

            changed = self.repository.reassign_module_references(dedupe_ids, canonical_id)
            for table, count in changed.items():
                reassigned_counts[table] = reassigned_counts.get(table, 0) + count
            self.repository.delete_modules(dedupe_ids)
            deleted_modules.extend(modules_by_id[module_id] for module_id in dedupe_ids)

        if not deleted_modules:
            return CommandResult(success=False, message="No duplicate modules were removed.")

        deleted_lines = "\n".join(
            f"- #{module.id[:8]} {module.name}{_module_code_label(module)}"
            for module in deleted_modules
        )
        reassigned_total = sum(reassigned_counts.values())
        return CommandResult(
            success=True,
            message=(
                f"Duplicate modules removed: {len(deleted_modules)}\n"
                f"References reassigned: {reassigned_total}\n\n"
                f"{deleted_lines}"
            ),
        )

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
        fatigue_level: str | FatigueLevel = FatigueLevel.MEDIUM,
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
                fatigue_level=fatigue_level,
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

    def add_module(
        self,
        name: str,
        code: str | None = None,
        lecturer: str | None = None,
        notes: str | None = None,
    ) -> CommandResult:
        """Create a study module with validation."""

        validated_name = validate_text_field(name, required=True)
        if not validated_name:
            return CommandResult(success=False, message="Module name is required.")
        if validated_name is None:
            return CommandResult(success=False, message="Module name exceeds 200 characters.")

        validated_code = validate_text_field(code, max_length=50)
        validated_lecturer = validate_text_field(lecturer, max_length=100)
        validated_notes = validate_notes(notes)

        existing = self.repository.find_duplicate_module(validated_name, validated_code)
        if existing is not None:
            return CommandResult(
                success=False,
                message=f"Module already exists: #{existing.id} — {existing.name}",
            )

        module = self.create_module(
            name=validated_name,
            code=validated_code,
            lecturer=validated_lecturer,
            notes=validated_notes,
        )
        label = f" — {module.code}" if module.code else ""
        return CommandResult(
            success=True,
            message=f"Module added\n\n#{module.id[:8]}{label} — {module.name}",
            record_id=module.id,
        )

    def add_class_session(
        self,
        title: str,
        weekday: int,
        start_time: str,
        end_time: str,
        module_id: str | None = None,
        location: str | None = None,
        notes: str | None = None,
    ) -> CommandResult:
        """Create a weekly class session with validation."""

        validated_title = validate_text_field(title, required=True)
        if not validated_title:
            return CommandResult(success=False, message="Class title is required.")
        if validated_title is None:
            return CommandResult(success=False, message="Class title exceeds 200 characters.")

        if not (0 <= weekday <= 6):
            return CommandResult(success=False, message="Weekday must be 0-6 (Mon=0, Sun=6).")

        try:
            parse_hhmm(start_time)
        except ValueError:
            return CommandResult(success=False, message="start_time must be HH:MM format.")
        try:
            parse_hhmm(end_time)
        except ValueError:
            return CommandResult(success=False, message="end_time must be HH:MM format.")

        if parse_hhmm(start_time) >= parse_hhmm(end_time):
            return CommandResult(success=False, message="start_time must be before end_time.")

        if module_id:
            module = self.repository.get_module_by_id(module_id)
            if module is None:
                return CommandResult(success=False, message=f"Module #{module_id} not found.")

        validated_location = validate_text_field(location, max_length=200)
        validated_notes = validate_notes(notes)

        existing = self.repository.find_duplicate_class_session(
            validated_title, weekday, start_time, end_time
        )
        if existing is not None:
            return CommandResult(
                success=False,
                message=f"Class session already exists: {existing.title} on {_weekday_name(weekday)} {start_time}-{end_time}",
            )

        session = self.create_class_session(
            title=validated_title,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            module_id=module_id,
            location=validated_location,
            notes=validated_notes,
        )
        day_label = _weekday_name(weekday)
        return CommandResult(
            success=True,
            message=f"Class added\n\n{session.title}\n{day_label} {start_time}\u2013{end_time}",
            record_id=session.id,
        )

    def add_work_shift(
        self,
        title: str,
        start_at: str | datetime,
        end_at: str | datetime,
        location: str | None = None,
        role: str | None = None,
        energy_cost: int | None = None,
        fatigue_level: str | FatigueLevel = FatigueLevel.MEDIUM,
        notes: str | None = None,
    ) -> CommandResult:
        """Create a dated work shift with validation."""

        validated_title = validate_text_field(title or "Work", max_length=200)
        if not validated_title:
            validated_title = "Work"

        if isinstance(start_at, str):
            parsed_start, err = parse_datetime_strict(start_at, self.timezone)
            if err:
                return CommandResult(success=False, message=err)
        else:
            parsed_start = ensure_local_datetime(start_at, self.timezone)

        if isinstance(end_at, str):
            parsed_end, err = parse_datetime_strict(end_at, self.timezone)
            if err:
                return CommandResult(success=False, message=err)
        else:
            parsed_end = ensure_local_datetime(end_at, self.timezone)

        if parsed_start >= parsed_end:
            return CommandResult(success=False, message="start_at must be before end_at.")

        if energy_cost is not None:
            validated_energy = validate_energy_cost(energy_cost)
            if validated_energy is None:
                return CommandResult(success=False, message="energy_cost must be between 1 and 5.")
        else:
            validated_energy = None

        validated_fatigue = validate_fatigue_level(fatigue_level)
        if validated_fatigue is None:
            return CommandResult(
                success=False,
                message="fatigue_level must be one of: low, medium, high.",
            )

        validated_location = validate_text_field(location, max_length=200)
        validated_role = validate_text_field(role, max_length=100)
        validated_notes = validate_notes(notes)

        start_iso = parsed_start.isoformat()
        end_iso = parsed_end.isoformat()
        existing = self.repository.find_duplicate_work_shift(validated_title, start_iso, end_iso)
        if existing is not None:
            return CommandResult(
                success=False,
                message=f"Work shift already exists: {existing.title} on {parsed_start.strftime('%a %d %b %H:%M')}",
            )

        shift = self.create_work_shift(
            title=validated_title,
            start_at=parsed_start,
            end_at=parsed_end,
            location=validated_location,
            role=validated_role,
            energy_cost=validated_energy,
            fatigue_level=validated_fatigue,
            notes=validated_notes,
        )
        date_label = parsed_start.strftime("%a %d %b")
        time_label = f"{parsed_start.strftime('%H:%M')}\u2013{parsed_end.strftime('%H:%M')}"
        return CommandResult(
            success=True,
            message=f"Work shift added\n\n{date_label}\n{time_label}\nFatigue: {shift.fatigue_level.value}",
            record_id=shift.id,
        )

    def add_assignment(
        self,
        title: str,
        due_at: str | datetime | date,
        module_id: str | None = None,
        priority: int = 3,
        status: str = "todo",
        weight: float | None = None,
        estimated_hours: float | None = None,
        completed_hours: float = 0,
        notes: str | None = None,
    ) -> CommandResult:
        """Create an assignment with validation."""

        validated_title = validate_text_field(title, required=True)
        if not validated_title:
            return CommandResult(success=False, message="Assignment title is required.")
        if validated_title is None:
            return CommandResult(success=False, message="Assignment title exceeds 200 characters.")

        if isinstance(due_at, str):
            parsed_due, err = parse_datetime_input(due_at, self.timezone)
            if err:
                return CommandResult(success=False, message=err)
        else:
            parsed_due = parse_due_at(due_at, self.timezone)

        if module_id:
            module = self.repository.get_module_by_id(module_id)
            if module is None:
                return CommandResult(success=False, message=f"Module #{module_id} not found.")

        validated_priority = validate_priority(priority)
        if validated_priority is None:
            return CommandResult(success=False, message="Priority must be between 1 and 5.")

        validated_status = validate_status(status)
        if validated_status is None:
            allowed = ", ".join(sorted(ALLOWED_STATUSES))
            return CommandResult(success=False, message=f"Invalid status. Allowed: {allowed}")

        if weight is not None:
            validated_weight = validate_weight(weight)
            if validated_weight is None:
                return CommandResult(success=False, message="Weight must be between 0 and 100.")
        else:
            validated_weight = None

        if estimated_hours is not None:
            validated_estimate = validate_hours(estimated_hours)
            if validated_estimate is None:
                return CommandResult(success=False, message="estimated_hours must be >= 0.")
        else:
            validated_estimate = None

        validated_completed = validate_hours(completed_hours)
        if validated_completed is None:
            return CommandResult(success=False, message="completed_hours must be >= 0.")

        validated_notes = validate_notes(notes)

        due_iso = parsed_due.isoformat()
        existing = self.repository.find_duplicate_assignment(validated_title, due_iso)
        if existing is not None:
            return CommandResult(
                success=False,
                message=f"Assignment already exists: {existing.title} due {parsed_due.strftime('%a %d %b %H:%M')}",
            )

        assignment = self.create_assignment(
            title=validated_title,
            due_at=parsed_due,
            module_id=module_id,
            status=AssignmentStatus(validated_status),
            priority=validated_priority,
            weight=validated_weight,
            estimated_hours=validated_estimate,
            completed_hours=validated_completed,
            notes=validated_notes,
        )
        due_label = parsed_due.strftime("%a %d %b %H:%M")
        estimate_label = f"\nEstimate: {validated_estimate}h" if validated_estimate else ""
        return CommandResult(
            success=True,
            message=f"Assignment added\n\n#{assignment.id[:8]} \u2014 {assignment.title}\nDue: {due_label}\nPriority: {validated_priority}{estimate_label}",
            record_id=assignment.id,
        )

    def update_assignment_status(self, assignment_id: str, status: str) -> CommandResult:
        """Update assignment status with validation."""

        validated_status = validate_status(status)
        if validated_status is None:
            allowed = ", ".join(sorted(ALLOWED_STATUSES))
            return CommandResult(success=False, message=f"Invalid status. Allowed: {allowed}")

        assignment = self.repository.get_assignment_by_id(assignment_id)
        if assignment is None:
            return CommandResult(success=False, message=f"Assignment #{assignment_id} not found.")

        updated = self.repository.update_assignment_status(assignment_id, AssignmentStatus(validated_status))
        if not updated:
            return CommandResult(success=False, message="Failed to update assignment.")

        return CommandResult(
            success=True,
            message=f"Assignment updated\n\n#{assignment_id[:8]} \u2014 {assignment.title}\nStatus: {validated_status}",
            record_id=assignment_id,
        )

    def update_completed_hours(self, assignment_id: str, completed_hours: float) -> CommandResult:
        """Update assignment completed hours with validation."""

        validated_hours = validate_hours(completed_hours)
        if validated_hours is None:
            return CommandResult(success=False, message="completed_hours must be >= 0.")

        assignment = self.repository.get_assignment_by_id(assignment_id)
        if assignment is None:
            return CommandResult(success=False, message=f"Assignment #{assignment_id} not found.")

        updated = self.repository.update_completed_hours(assignment_id, validated_hours)
        if not updated:
            return CommandResult(success=False, message="Failed to update hours.")

        remaining = max(0, (assignment.estimated_hours or 0) - validated_hours)
        remaining_label = f"\nRemaining: {remaining}h" if assignment.estimated_hours else ""
        return CommandResult(
            success=True,
            message=f"Progress updated\n\n#{assignment_id[:8]} \u2014 {assignment.title}\nCompleted: {validated_hours}h{remaining_label}",
            record_id=assignment_id,
        )

    def list_all_assignments(self, include_completed: bool = True) -> list[Assignment]:
        """Return all assignments."""

        return self.repository.list_all_assignments(include_completed=include_completed)

    def list_all_work_shifts(self, limit: int = 50) -> list[WorkShift]:
        """Return upcoming work shifts."""

        return self.repository.list_all_work_shifts(limit=limit)


def _weekday_name(weekday: int) -> str:
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]


def _normalize_module_label(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _module_duplicate_key(module: StudyModule) -> tuple[str, str]:
    return (
        _normalize_module_label(module.name),
        _normalize_module_label(module.code or ""),
    )


def _module_code_label(module: StudyModule) -> str:
    return f" ({module.code})" if module.code else ""


def _unique_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        module_id = str(value).strip()
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)
        unique.append(module_id)
    return unique


def get_academic_service() -> AcademicService:
    """Deprecated: construct AcademicService with injected app settings."""

    raise RuntimeError("AcademicService requires injected db_path and timezone settings.")


def _duration_minutes(start_at: datetime, end_at: datetime) -> int:
    return int((end_at - start_at).total_seconds() // 60)
