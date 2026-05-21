"""Read-only service-backed views for the Atenas terminal UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config import Settings, get_settings
from app.tui.models import TuiRow, TuiSection, TuiView
from core.academic.models import Assignment, TimeBlock
from core.academic.planner import PlannedStudyBlock, StudyPlan
from core.academic.service import AcademicService
from core.db import init_db
from core.knowledge.models import FileRecord, Note, SearchResult
from core.knowledge.service import KnowledgeService


@dataclass(frozen=True)
class TuiContext:
    """Runtime dependencies for read-only TUI views."""

    settings: Settings
    academic: AcademicService
    knowledge: KnowledgeService


def build_tui_context(settings: Settings | None = None) -> TuiContext:
    """Initialize local storage and build service dependencies."""

    runtime_settings = settings or get_settings()
    _ensure_runtime_dirs(runtime_settings)
    init_db(runtime_settings.db_path)
    return TuiContext(
        settings=runtime_settings,
        academic=AcademicService(runtime_settings.db_path, timezone=runtime_settings.timezone),
        knowledge=KnowledgeService(
            runtime_settings.db_path,
            timezone=runtime_settings.timezone,
            allowed_file_roots=runtime_settings.knowledge_file_roots,
        ),
    )


def load_view(context: TuiContext, key: str, *, search_query: str = "") -> TuiView:
    """Load a read-only view by key."""

    builders = {
        "home": _home_view,
        "today": _today_view,
        "week": _week_view,
        "plan": _plan_view,
        "deadlines": _deadlines_view,
        "data": _data_view,
        "knowledge": _knowledge_view,
        "search": lambda inner: _search_view(inner, search_query),
    }
    builder = builders.get(key, _home_view)
    return builder(context)


def _home_view(context: TuiContext) -> TuiView:
    settings = context.settings
    modules = context.academic.list_modules()
    assignments = context.academic.list_all_assignments(include_completed=False)
    notes = context.knowledge.list_notes(limit=5)
    files = context.knowledge.list_files(limit=5)
    rows = (
        TuiRow(("Database", str(settings.db_path))),
        TuiRow(("Timezone", settings.timezone)),
        TuiRow(("Modules", str(len(modules)))),
        TuiRow(("Open assignments", str(len(assignments)))),
        TuiRow(("Latest notes", f"{len(notes)} shown")),
        TuiRow(("Latest files", f"{len(files)} shown")),
        TuiRow(("Keys", "1-8 tabs, arrows move, / search, r refresh, q quit")),
    )
    return TuiView(
        key="home",
        title=settings.app_name,
        subtitle="local read-only terminal UI",
        sections=(TuiSection("Runtime", rows),),
    )


def _today_view(context: TuiContext) -> TuiView:
    overview = context.academic.get_today_overview()
    return TuiView(
        key="today",
        title="Today",
        subtitle=overview.date.strftime("%a %d %b %Y"),
        sections=(
            TuiSection("Classes", _time_block_rows(overview.classes), "No classes today."),
            TuiSection("Work", _time_block_rows(overview.work_shifts), "No shifts today."),
            TuiSection("Deadlines", _assignment_rows(overview.deadlines), "No imminent deadlines."),
            TuiSection(
                "Study Windows",
                tuple(
                    TuiRow(
                        (
                            _time_range(window.start_at, window.end_at),
                            _minutes_label(window.minutes),
                            window.max_intensity,
                        )
                    )
                    for window in overview.availability.study_windows
                ),
                "No study windows left today.",
            ),
        ),
    )


def _week_view(context: TuiContext) -> TuiView:
    overview = context.academic.get_week_overview()
    rows = tuple(
        TuiRow(
            (
                summary.date.strftime("%a %d %b"),
                f"class {_minutes_label(summary.class_minutes)}",
                f"work {_minutes_label(summary.work_minutes)}",
                f"study {_minutes_label(summary.study_minutes)}",
            )
        )
        for summary in overview.day_summaries
    )
    totals = (
        TuiRow(("Classes", str(overview.class_count))),
        TuiRow(("Work shifts", str(overview.work_shift_count))),
        TuiRow(("Open deadlines this week", str(overview.open_deadline_count))),
        TuiRow(("Available study", _minutes_label(overview.availability.total_study_minutes))),
    )
    return TuiView(
        key="week",
        title="Week",
        subtitle=f"{overview.start_date.isoformat()} to {overview.end_date.isoformat()}",
        sections=(TuiSection("Summary", totals), TuiSection("Days", rows)),
    )


def _plan_view(context: TuiContext) -> TuiView:
    plan = context.academic.get_study_plan()
    summary = plan.summary
    sections = [
        TuiSection(
            "Capacity",
            (
                TuiRow(("Available", _minutes_label(summary.total_available_minutes))),
                TuiRow(("Required", _minutes_label(summary.total_required_minutes))),
                TuiRow(("Planned", _minutes_label(summary.total_planned_minutes))),
                TuiRow(("Unscheduled", _minutes_label(summary.total_unscheduled_minutes))),
            ),
        ),
        TuiSection("Blocks", _plan_block_rows(plan.blocks), "No planned study blocks."),
        TuiSection(
            "Warnings",
            tuple(TuiRow((warning,)) for warning in _plan_warnings(plan)),
            "No planning warnings.",
        ),
    ]
    return TuiView(
        key="plan",
        title="Plan",
        subtitle=f"{plan.start_date.isoformat()} to {plan.end_date.isoformat()}",
        sections=tuple(sections),
    )


def _deadlines_view(context: TuiContext) -> TuiView:
    assignments = context.academic.list_upcoming_assignments(limit=30, include_completed=False)
    return TuiView(
        key="deadlines",
        title="Deadlines",
        subtitle="open upcoming assignments",
        sections=(TuiSection("Assignments", _assignment_rows(assignments), "No open deadlines."),),
    )


def _data_view(context: TuiContext) -> TuiView:
    modules = context.academic.list_modules()
    classes = context.academic.list_class_sessions()
    shifts = context.academic.list_all_work_shifts(limit=12)
    assignments = context.academic.list_all_assignments(include_completed=False)
    return TuiView(
        key="data",
        title="Data",
        subtitle="academic records",
        sections=(
            TuiSection(
                "Modules",
                tuple(TuiRow((_short_id(module.id), module.name, module.code or "")) for module in modules),
                "No modules found.",
            ),
            TuiSection(
                "Classes",
                tuple(
                    TuiRow((_weekday_label(session.weekday), f"{session.start_time}-{session.end_time}", session.title))
                    for session in classes
                ),
                "No active classes found.",
            ),
            TuiSection(
                "Upcoming Shifts",
                tuple(TuiRow((shift.start_at.strftime("%a %d %b %H:%M"), shift.title)) for shift in shifts),
                "No shifts found.",
            ),
            TuiSection(
                "Open Assignments",
                tuple(TuiRow((_short_id(item.id), item.title, item.status.value)) for item in assignments),
                "No open assignments found.",
            ),
        ),
    )


def _knowledge_view(context: TuiContext) -> TuiView:
    notes = context.knowledge.list_notes(limit=20)
    files = context.knowledge.list_files(limit=20)
    return TuiView(
        key="knowledge",
        title="Knowledge",
        subtitle="latest notes and files",
        sections=(
            TuiSection("Notes", _note_rows(notes), "No notes found."),
            TuiSection("Files", _file_rows(files), "No files found."),
        ),
    )


def _search_view(context: TuiContext, search_query: str) -> TuiView:
    query = search_query.strip()
    if not query:
        rows: tuple[TuiRow, ...] = ()
        empty = "Press / and enter at least two characters to search notes and files."
    else:
        results, error = context.knowledge.search(query=query, limit=20)
        rows = _search_rows(results)
        empty = error or "No results."
    return TuiView(
        key="search",
        title="Search",
        subtitle=f'query "{query}"' if query else "local notes/files",
        sections=(TuiSection("Results", rows, empty),),
    )


def _ensure_runtime_dirs(settings: Settings) -> None:
    paths: list[Path] = [
        settings.data_dir,
        settings.memory_dir,
        settings.output_dir,
        settings.inbox_dir,
        settings.logs_dir,
        *settings.knowledge_file_roots,
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _time_block_rows(blocks: Iterable[TimeBlock]) -> tuple[TuiRow, ...]:
    return tuple(TuiRow((_time_range(block.start_at, block.end_at), block.title)) for block in blocks)


def _assignment_rows(assignments: Iterable[Assignment]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow(
            (
                _short_id(assignment.id),
                assignment.title,
                assignment.due_at.strftime("%a %d %b %H:%M"),
                f"priority {assignment.priority}",
                assignment.status.value,
            ),
            emphasis=assignment.priority <= 2,
        )
        for assignment in assignments
    )


def _plan_block_rows(blocks: Iterable[PlannedStudyBlock]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow(
            (
                block.start_at.strftime("%a %d %b"),
                _time_range(block.start_at, block.end_at),
                block.assignment_title,
                _minutes_label(block.minutes),
                block.reason,
            ),
            emphasis=block.priority <= 2,
        )
        for block in blocks
    )


def _plan_warnings(plan: StudyPlan) -> list[str]:
    warnings: list[str] = []
    warnings.extend(f"Unestimated: {title}" for title in plan.summary.unestimated_assignments)
    warnings.extend(f"Overdue: {title}" for title in plan.summary.overdue_assignments)
    warnings.extend(
        f"Unscheduled: {item.assignment_title} needs {_minutes_label(item.unscheduled_minutes)}"
        for item in plan.unscheduled
    )
    return warnings


def _note_rows(notes: Iterable[Note]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow((f"#{note.id}", note.title, ", ".join(note.tags))) for note in notes if note.id is not None
    )


def _file_rows(files: Iterable[FileRecord]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow((f"#{record.id}", record.title or record.filename, record.file_type or "file"))
        for record in files
        if record.id is not None
    )


def _search_rows(results: Iterable[SearchResult]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow((result.kind, f"#{result.id}", result.title, result.snippet))
        for result in results
    )


def _time_range(start_at, end_at) -> str:
    return f"{start_at.strftime('%H:%M')}-{end_at.strftime('%H:%M')}"


def _minutes_label(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h{remainder:02d}"
    if hours:
        return f"{hours}h"
    return f"{remainder}m"


def _short_id(value: str) -> str:
    return f"#{value[:8]}"


def _weekday_label(weekday: int) -> str:
    labels = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    if 0 <= weekday < len(labels):
        return labels[weekday]
    return str(weekday)
