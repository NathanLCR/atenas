# Atenas TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local terminal UI for Atenas so Nathan can inspect schedule, planning, deadlines, modules, assignments, notes, files, and local search without starting the web dashboard.

**Architecture:** Build the TUI as an `app/` support surface over existing `core/` services, matching the current dashboard's local support role. Keep the first version read-only: the terminal UI must not call the LLM agent loop or execute act tools, because those paths need an explicit actor/confirmation/audit contract before writes are safe outside Telegram. Split it into pure view-model and rendering modules with a very thin `curses` runtime so most behavior is covered by normal pytest tests.

**Tech Stack:** Python 3.11, standard-library `curses`, dataclasses, existing `AcademicService` and `KnowledgeService`, SQLite, pytest.

---

## Scope

Ship a read-only MVP TUI with these tabs:

- Home: app/runtime summary and key hints.
- Today: classes, shifts, imminent deadlines, available study windows.
- Week: Monday-Sunday summary.
- Plan: deterministic study plan blocks and warnings.
- Deadlines: open upcoming assignments.
- Data: modules, active classes, upcoming shifts, open assignments.
- Knowledge: latest notes and files.
- Search: local notes/files keyword search after pressing `/`.

Do not add write forms, confirmation prompts, NL chat, web search, export, or external-provider calls in this plan. Those need a separate governance plan.

## File Structure

Create:

- `app/tui/__init__.py` - package marker and small public export.
- `app/tui/__main__.py` - `python -m app.tui` entrypoint.
- `app/tui/models.py` - small immutable display models used by view builders and renderer.
- `app/tui/view_model.py` - service-backed read-only view builders.
- `app/tui/render.py` - pure text layout renderer with width/height clipping.
- `app/tui/controller.py` - tab/search/refresh state machine independent from curses.
- `app/tui/runtime.py` - curses integration, drawing, key mapping, search prompt.
- `tests/test_tui_view_model.py` - service-backed view builder tests.
- `tests/test_tui_render.py` - pure renderer tests.
- `tests/test_tui_controller.py` - state machine tests.
- `tests/test_tui_runtime.py` - key mapping and entrypoint wiring tests.

Modify:

- `README.md` - add run command and describe read-only TUI posture.
- `docs/README.md` - add TUI to the local support surfaces list.

Do not modify:

- `requirements.txt` - no dependency is needed for the MVP TUI.
- `core/` architecture direction - the new dependency is `app/tui -> core`, never `core -> app`.

---

## Task 1: Add TUI Display Models

**Files:**
- Create: `app/tui/__init__.py`
- Create: `app/tui/models.py`
- Create: `tests/test_tui_render.py`

- [ ] **Step 1: Write failing renderer-oriented model tests**

Create `tests/test_tui_render.py`:

```python
from app.tui.models import TuiRow, TuiSection, TuiView
from app.tui.render import render_view


def test_render_view_includes_tabs_and_sections() -> None:
    view = TuiView(
        key="today",
        title="Today",
        subtitle="Thu 21 May",
        sections=(
            TuiSection(
                title="Deadlines",
                rows=(
                    TuiRow(("NLP CA1", "due 23:59")),
                ),
            ),
        ),
    )

    lines = render_view(
        view,
        tabs=(("home", "Home"), ("today", "Today")),
        active_key="today",
        width=60,
        height=12,
        status="q quit",
    )

    joined = "\n".join(lines)
    assert "[Today]" in joined
    assert "Thu 21 May" in joined
    assert "Deadlines" in joined
    assert "NLP CA1" in joined
    assert "q quit" in lines[-1]


def test_render_view_clips_to_dimensions() -> None:
    view = TuiView(
        key="knowledge",
        title="Knowledge",
        sections=(
            TuiSection(
                title="Notes",
                rows=tuple(TuiRow((f"Long note title {index}", "manual")) for index in range(20)),
            ),
        ),
    )

    lines = render_view(
        view,
        tabs=(("knowledge", "Knowledge"),),
        active_key="knowledge",
        width=24,
        height=8,
        status="ready",
    )

    assert len(lines) == 8
    assert all(len(line) <= 24 for line in lines)
    assert lines[-1].strip() == "ready"
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_tui_render.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.tui'`.

- [ ] **Step 3: Create the TUI package marker**

Create `app/tui/__init__.py`:

```python
"""Local read-only terminal UI for Atenas."""

__all__: list[str] = []
```

- [ ] **Step 4: Create immutable display models**

Create `app/tui/models.py`:

```python
"""Display models for the Atenas terminal UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiRow:
    """A single display row inside a section."""

    cells: tuple[str, ...]
    emphasis: bool = False


@dataclass(frozen=True)
class TuiSection:
    """A titled group of rows."""

    title: str
    rows: tuple[TuiRow, ...] = ()
    empty_message: str = "Nothing to show."


@dataclass(frozen=True)
class TuiView:
    """One full-screen TUI tab."""

    key: str
    title: str
    subtitle: str = ""
    sections: tuple[TuiSection, ...] = ()
    empty_message: str = "Nothing to show."


DEFAULT_TABS: tuple[tuple[str, str], ...] = (
    ("home", "Home"),
    ("today", "Today"),
    ("week", "Week"),
    ("plan", "Plan"),
    ("deadlines", "Deadlines"),
    ("data", "Data"),
    ("knowledge", "Knowledge"),
    ("search", "Search"),
)
```

Do not run the test yet; `render_view` still does not exist.

---

## Task 2: Add A Pure Renderer

**Files:**
- Create: `app/tui/render.py`
- Modify: `tests/test_tui_render.py`

- [ ] **Step 1: Add an empty-state renderer test**

Append this test to `tests/test_tui_render.py`:

```python
def test_render_view_shows_empty_message() -> None:
    view = TuiView(key="plan", title="Plan", empty_message="No planned blocks.")

    lines = render_view(
        view,
        tabs=(("plan", "Plan"),),
        active_key="plan",
        width=50,
        height=8,
        status="ready",
    )

    joined = "\n".join(lines)
    assert "No planned blocks." in joined
```

- [ ] **Step 2: Run renderer tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_tui_render.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.tui.render'`.

- [ ] **Step 3: Implement `render_view`**

Create `app/tui/render.py`:

```python
"""Pure text rendering for the Atenas terminal UI."""

from __future__ import annotations

from app.tui.models import TuiRow, TuiSection, TuiView

MIN_WIDTH = 32
MIN_HEIGHT = 6


def render_view(
    view: TuiView,
    *,
    tabs: tuple[tuple[str, str], ...],
    active_key: str,
    width: int,
    height: int,
    status: str,
) -> list[str]:
    """Render a TUI view into clipped terminal lines."""

    width = max(MIN_WIDTH, width)
    height = max(MIN_HEIGHT, height)
    body_height = height - 1
    lines: list[str] = [
        _tab_bar(tabs, active_key),
        _rule(width),
        view.title if not view.subtitle else f"{view.title} - {view.subtitle}",
        "",
    ]

    if view.sections:
        for section in view.sections:
            _append_section(lines, section)
    else:
        lines.append(view.empty_message)

    clipped_body = [_clip(line, width) for line in lines[:body_height]]
    while len(clipped_body) < body_height:
        clipped_body.append("")
    return [*clipped_body, _clip(status, width)]


def _append_section(lines: list[str], section: TuiSection) -> None:
    lines.append(section.title)
    if not section.rows:
        lines.append(f"  {section.empty_message}")
        lines.append("")
        return
    for row in section.rows:
        lines.append(_row_text(row))
    lines.append("")


def _row_text(row: TuiRow) -> str:
    prefix = "* " if row.emphasis else "  "
    return prefix + " | ".join(str(cell) for cell in row.cells)


def _tab_bar(tabs: tuple[tuple[str, str], ...], active_key: str) -> str:
    labels = []
    for key, label in tabs:
        labels.append(f"[{label}]" if key == active_key else label)
    return "  ".join(labels)


def _rule(width: int) -> str:
    return "-" * width


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "~"
```

- [ ] **Step 4: Run renderer tests and verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_tui_render.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit renderer foundation**

Run:

```bash
git add app/tui/__init__.py app/tui/models.py app/tui/render.py tests/test_tui_render.py
git commit -m "feat: add tui display renderer"
```

---

## Task 3: Build Service-Backed Read-Only Views

**Files:**
- Create: `app/tui/view_model.py`
- Create: `tests/test_tui_view_model.py`

- [ ] **Step 1: Write failing view-model tests**

Create `tests/test_tui_view_model.py`:

```python
from pathlib import Path

from app.config import Settings
from app.tui.view_model import build_tui_context, load_view
from core.academic.service import AcademicService
from core.db import init_db
from core.knowledge.service import KnowledgeService


def test_home_view_summarizes_runtime_state(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    AcademicService(settings.db_path, timezone=settings.timezone).add_module(name="Deep Learning", code="DL")

    context = build_tui_context(settings)
    view = load_view(context, "home")

    text = _view_text(view)
    assert view.title == "Atenas"
    assert "Modules" in text
    assert "1" in text
    assert str(settings.db_path) in text


def test_deadlines_view_lists_open_assignments(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    service.add_assignment(
        title="NLP CA1",
        due_at="2026-05-22 23:59",
        priority=2,
        estimated_hours=4,
    )

    context = build_tui_context(settings)
    view = load_view(context, "deadlines")

    text = _view_text(view)
    assert "NLP CA1" in text
    assert "priority 2" in text


def test_knowledge_view_lists_notes_and_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    service = KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
    service.create_note(title="CNN notes", body="Convolutions and pooling", tags=["ml"])

    context = build_tui_context(settings)
    view = load_view(context, "knowledge")

    text = _view_text(view)
    assert "CNN notes" in text
    assert "ml" in text


def test_search_view_uses_local_keyword_search(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    service = KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
    service.create_note(title="Transformers", body="Attention layers and embeddings")

    context = build_tui_context(settings)
    view = load_view(context, "search", search_query="attention")

    text = _view_text(view)
    assert "Transformers" in text
    assert "attention" in view.subtitle.lower()


def test_unknown_view_falls_back_to_home(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    context = build_tui_context(settings)
    view = load_view(context, "nope")

    assert view.key == "home"


def _settings(tmp_path: Path) -> Settings:
    inbox = tmp_path / "inbox"
    memory = tmp_path / "memory"
    inbox.mkdir()
    memory.mkdir()
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=memory,
        output_dir=tmp_path / "output",
        inbox_dir=inbox,
        logs_dir=tmp_path / "logs",
        knowledge_file_roots=[inbox, memory],
    )


def _view_text(view) -> str:
    return "\n".join(
        " ".join(row.cells)
        for section in view.sections
        for row in section.rows
    )
```

- [ ] **Step 2: Run view-model tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_tui_view_model.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.tui.view_model'`.

- [ ] **Step 3: Implement view builders**

Create `app/tui/view_model.py`:

```python
"""Read-only service-backed views for the Atenas terminal UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
        TuiRow(("Notes", str(len(notes)))),
        TuiRow(("Files", str(len(files)))),
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


def _time_block_rows(blocks: list[TimeBlock]) -> tuple[TuiRow, ...]:
    return tuple(TuiRow((_time_range(block.start_at, block.end_at), block.title)) for block in blocks)


def _assignment_rows(assignments: list[Assignment]) -> tuple[TuiRow, ...]:
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


def _plan_block_rows(blocks: list[PlannedStudyBlock]) -> tuple[TuiRow, ...]:
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


def _note_rows(notes: list[Note]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow((f"#{note.id}", note.title, ", ".join(note.tags))) for note in notes if note.id is not None
    )


def _file_rows(files: list[FileRecord]) -> tuple[TuiRow, ...]:
    return tuple(
        TuiRow((f"#{record.id}", record.title or record.filename, record.file_type or "file"))
        for record in files
        if record.id is not None
    )


def _search_rows(results: list[SearchResult]) -> tuple[TuiRow, ...]:
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
```

- [ ] **Step 4: Run view-model tests and renderer tests**

Run:

```bash
.venv/bin/pytest tests/test_tui_view_model.py tests/test_tui_render.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit view builders**

Run:

```bash
git add app/tui/view_model.py tests/test_tui_view_model.py
git commit -m "feat: add tui read models"
```

---

## Task 4: Add A Testable TUI Controller

**Files:**
- Create: `app/tui/controller.py`
- Create: `tests/test_tui_controller.py`

- [ ] **Step 1: Write failing controller tests**

Create `tests/test_tui_controller.py`:

```python
from pathlib import Path

from app.config import Settings
from app.tui.controller import TuiController
from app.tui.models import DEFAULT_TABS
from app.tui.view_model import build_tui_context


def test_controller_starts_on_home(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.active_key == "home"
    assert controller.current_view().key == "home"


def test_controller_switches_tabs_by_command(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.handle_command("tab:plan") is True

    assert controller.active_key == "plan"
    assert controller.current_view().key == "plan"


def test_controller_ignores_unknown_tab(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.handle_command("tab:nope") is True

    assert controller.active_key == "home"
    assert "Unknown tab" in controller.status_message


def test_controller_search_sets_query_and_tab(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    controller.set_search_query("attention")

    assert controller.active_key == "search"
    assert controller.search_query == "attention"
    assert "attention" in controller.current_view().subtitle


def test_controller_quit_returns_false(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.handle_command("quit") is False


def test_default_tabs_are_number_addressable() -> None:
    assert len(DEFAULT_TABS) <= 9


def _settings(tmp_path: Path) -> Settings:
    inbox = tmp_path / "inbox"
    memory = tmp_path / "memory"
    inbox.mkdir()
    memory.mkdir()
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=memory,
        output_dir=tmp_path / "output",
        inbox_dir=inbox,
        logs_dir=tmp_path / "logs",
        knowledge_file_roots=[inbox, memory],
    )
```

- [ ] **Step 2: Run controller tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_tui_controller.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.tui.controller'`.

- [ ] **Step 3: Implement controller**

Create `app/tui/controller.py`:

```python
"""State machine for the Atenas terminal UI."""

from __future__ import annotations

from dataclasses import dataclass

from app.tui.models import DEFAULT_TABS, TuiView
from app.tui.view_model import TuiContext, load_view


@dataclass
class TuiController:
    """Hold active tab and search state without depending on curses."""

    context: TuiContext
    tabs: tuple[tuple[str, str], ...] = DEFAULT_TABS
    active_index: int = 0
    search_query: str = ""
    status_message: str = "1-8 tabs | arrows move | / search | r refresh | q quit"

    @property
    def active_key(self) -> str:
        return self.tabs[self.active_index][0]

    def current_view(self) -> TuiView:
        return load_view(self.context, self.active_key, search_query=self.search_query)

    def handle_command(self, command: str) -> bool:
        if command == "quit":
            return False
        if command == "next_tab":
            self.active_index = (self.active_index + 1) % len(self.tabs)
            self.status_message = self._tab_status()
            return True
        if command == "previous_tab":
            self.active_index = (self.active_index - 1) % len(self.tabs)
            self.status_message = self._tab_status()
            return True
        if command == "refresh":
            self.status_message = "Refreshed."
            return True
        if command.startswith("tab:"):
            self._set_active_key(command.removeprefix("tab:"))
            return True
        return True

    def set_search_query(self, query: str) -> None:
        self.search_query = query.strip()
        self._set_active_key("search")
        if self.search_query:
            self.status_message = f'Search: "{self.search_query}"'
        else:
            self.status_message = "Search cleared."

    def _set_active_key(self, key: str) -> None:
        for index, (tab_key, label) in enumerate(self.tabs):
            if tab_key == key:
                self.active_index = index
                self.status_message = f"Tab: {label}"
                return
        self.status_message = f"Unknown tab: {key}"

    def _tab_status(self) -> str:
        return f"Tab: {self.tabs[self.active_index][1]}"
```

- [ ] **Step 4: Run controller tests**

Run:

```bash
.venv/bin/pytest tests/test_tui_controller.py tests/test_tui_view_model.py tests/test_tui_render.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit controller**

Run:

```bash
git add app/tui/controller.py tests/test_tui_controller.py
git commit -m "feat: add tui controller"
```

---

## Task 5: Add Curses Runtime And Module Entrypoint

**Files:**
- Create: `app/tui/runtime.py`
- Create: `app/tui/__main__.py`
- Create: `tests/test_tui_runtime.py`
- Modify: `app/tui/__init__.py`

- [ ] **Step 1: Write failing runtime tests**

Create `tests/test_tui_runtime.py`:

```python
from app.tui.runtime import command_from_key


def test_command_from_key_maps_quit() -> None:
    assert command_from_key(ord("q")) == "quit"
    assert command_from_key(ord("Q")) == "quit"


def test_command_from_key_maps_refresh_and_search() -> None:
    assert command_from_key(ord("r")) == "refresh"
    assert command_from_key(ord("/")) == "search_prompt"


def test_command_from_key_maps_numbered_tabs() -> None:
    assert command_from_key(ord("1")) == "tab:home"
    assert command_from_key(ord("4")) == "tab:plan"
    assert command_from_key(ord("8")) == "tab:search"


def test_command_from_key_ignores_unknown_key() -> None:
    assert command_from_key(ord("x")) == "noop"
```

- [ ] **Step 2: Run runtime tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_tui_runtime.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.tui.runtime'`.

- [ ] **Step 3: Implement curses runtime**

Create `app/tui/runtime.py`:

```python
"""Curses runtime for the Atenas terminal UI."""

from __future__ import annotations

import curses

from app.config import Settings
from app.tui.controller import TuiController
from app.tui.models import DEFAULT_TABS
from app.tui.render import render_view
from app.tui.view_model import build_tui_context


def run(settings: Settings | None = None) -> None:
    """Run the terminal UI."""

    context = build_tui_context(settings)
    controller = TuiController(context)
    curses.wrapper(lambda stdscr: _run_loop(stdscr, controller))


def command_from_key(key: int) -> str:
    """Map a curses key code to a controller command."""

    if key in (ord("q"), ord("Q")):
        return "quit"
    if key in (ord("r"), ord("R")):
        return "refresh"
    if key == ord("/"):
        return "search_prompt"
    if key in (curses.KEY_RIGHT, ord("l"), ord("L")):
        return "next_tab"
    if key in (curses.KEY_LEFT, ord("h"), ord("H")):
        return "previous_tab"
    if ord("1") <= key <= ord(str(len(DEFAULT_TABS))):
        index = key - ord("1")
        return f"tab:{DEFAULT_TABS[index][0]}"
    return "noop"


def _run_loop(stdscr, controller: TuiController) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    while True:
        _draw(stdscr, controller)
        key = stdscr.getch()
        command = command_from_key(key)
        if command == "search_prompt":
            controller.set_search_query(_prompt(stdscr, "Search notes/files"))
            continue
        keep_running = controller.handle_command(command)
        if not keep_running:
            break


def _draw(stdscr, controller: TuiController) -> None:
    height, width = stdscr.getmaxyx()
    lines = render_view(
        controller.current_view(),
        tabs=controller.tabs,
        active_key=controller.active_key,
        width=width,
        height=height,
        status=controller.status_message,
    )
    stdscr.erase()
    for row, line in enumerate(lines):
        if row >= height:
            break
        stdscr.addnstr(row, 0, line, max(0, width - 1))
    stdscr.refresh()


def _prompt(stdscr, label: str) -> str:
    height, width = stdscr.getmaxyx()
    prompt = f"{label}: "
    curses.curs_set(1)
    curses.echo()
    try:
        stdscr.move(max(0, height - 1), 0)
        stdscr.clrtoeol()
        stdscr.addnstr(max(0, height - 1), 0, prompt, max(0, width - 1))
        value = stdscr.getstr(max(0, height - 1), len(prompt), max(1, width - len(prompt) - 1))
    finally:
        curses.noecho()
        curses.curs_set(0)
    return value.decode("utf-8", errors="replace").strip()
```

- [ ] **Step 4: Add module entrypoint**

Create `app/tui/__main__.py`:

```python
"""Run Atenas' local terminal UI with `python -m app.tui`."""

from app.tui.runtime import run


if __name__ == "__main__":
    run()
```

Replace `app/tui/__init__.py` with:

```python
"""Local read-only terminal UI for Atenas."""

from app.tui.runtime import run

__all__ = ["run"]
```

- [ ] **Step 5: Run runtime and TUI tests**

Run:

```bash
.venv/bin/pytest tests/test_tui_runtime.py tests/test_tui_controller.py tests/test_tui_view_model.py tests/test_tui_render.py -q
```

Expected: PASS.

- [ ] **Step 6: Smoke-test import without launching curses**

Run:

```bash
.venv/bin/python -c "from app.tui.runtime import command_from_key; print(command_from_key(ord('1')))"
```

Expected: prints `tab:home`.

- [ ] **Step 7: Manual local smoke test**

Run:

```bash
.venv/bin/python -m app.tui
```

Expected:

- Full-screen terminal UI opens.
- `1` through `8` switch tabs.
- Left/right arrows switch tabs.
- `/` prompts for a search query.
- `r` refreshes the current tab.
- `q` exits back to the shell.

- [ ] **Step 8: Commit runtime**

Run:

```bash
git add app/tui/runtime.py app/tui/__main__.py app/tui/__init__.py tests/test_tui_runtime.py
git commit -m "feat: add tui runtime"
```

---

## Task 6: Document The TUI Surface

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Add README test by inspection**

Run:

```bash
rg "python -m app.tui|read-only terminal" README.md docs/README.md
```

Expected before docs edit: no matches or missing one of the two files.

- [ ] **Step 2: Update `README.md` run instructions**

In `README.md`, after the existing FastAPI run command, add:

````markdown
### Terminal UI

Atenas also has a local read-only terminal UI for quick inspection without the
web dashboard:

```bash
.venv/bin/python -m app.tui
```

The TUI is a local support surface. It reads the same SQLite data through core
services and does not execute writes, LLM act tools, web search, or exports.
````

- [ ] **Step 3: Update `docs/README.md` support surfaces**

In `docs/README.md`, in the "Current direction" section, change:

```markdown
Dashboard/API are local support surfaces only.
```

to:

```markdown
Dashboard/API/TUI are local support surfaces only.
```

Then add this short paragraph after that section:

```markdown
The terminal UI runs with `.venv/bin/python -m app.tui`. It is read-only in its
first version and must not call act tools or the LLM agent loop until a separate
confirmation and audit contract exists for terminal-originated writes.
```

- [ ] **Step 4: Verify docs mention the command and posture**

Run:

```bash
rg "python -m app.tui|Dashboard/API/TUI|read-only" README.md docs/README.md
```

Expected: matches in both files.

- [ ] **Step 5: Commit docs**

Run:

```bash
git add README.md docs/README.md
git commit -m "docs: document local tui"
```

---

## Task 7: Final Verification

**Files:**
- No file changes expected unless verification finds a defect.

- [ ] **Step 1: Run focused TUI tests**

Run:

```bash
.venv/bin/pytest tests/test_tui_render.py tests/test_tui_view_model.py tests/test_tui_controller.py tests/test_tui_runtime.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 3: Verify no dependency change happened**

Run:

```bash
git diff -- requirements.txt
```

Expected: no output.

- [ ] **Step 4: Check file sizes stay reviewable**

Run:

```bash
wc -l app/tui/*.py tests/test_tui_*.py
```

Expected: every new source file stays under 500 lines.

- [ ] **Step 5: Manual TUI smoke test**

Run:

```bash
.venv/bin/python -m app.tui
```

Expected: the TUI opens, draws non-overlapping text, supports tab switching/search/refresh/quit, and exits cleanly.

- [ ] **Step 6: Final commit if verification required fixes**

If Step 1-5 required fixes, commit only those fixes:

```bash
git add app/tui tests README.md docs/README.md
git commit -m "fix: polish tui verification issues"
```

---

## Self-Review

Spec coverage:

- Adds a local TUI support surface without turning dashboard/API into remote product surfaces.
- Preserves `app -> core` dependency direction.
- Keeps v1 read-only so it cannot bypass Telegram allowlist, confirmation, action-tier gates, or audit policy.
- Uses deterministic core services for schedule/planning/knowledge reads.
- Adds focused tests that do not require a real terminal, Telegram, Ollama, or `.env`.

Placeholder scan:

- No placeholder language remains in the task steps.
- Every code-bearing step gives concrete test or implementation content.

Type consistency:

- `TuiController.current_view()` calls `load_view(context, active_key, search_query=...)`.
- `render_view()` receives `TuiView`, `tabs`, `active_key`, `width`, `height`, and `status` consistently.
- Runtime key mapping returns commands accepted by `TuiController.handle_command()`.

## Execution Handoff Prompt

Use this prompt in a fresh Codex session when ready to implement:

```text
Implement the plan at docs/superpowers/plans/2026-05-21-atenas-tui.md.

Use the required Superpowers execution skill from the plan: prefer superpowers:subagent-driven-development if available; otherwise use superpowers:executing-plans. Follow the plan task-by-task with the checkbox steps. Keep the first TUI read-only, use standard-library curses only, do not add requirements.txt dependencies, and preserve the app -> core dependency direction.

Before editing, read CLAUDE.md, docs/AGENT_LOOP.md, docs/ARCHITECTURE.md, docs/REQUIREMENTS.md, and the plan. Implement each task with its tests first, run the exact verification commands in the plan, and commit after each task using the specified commit messages. Do not wire the TUI to NL agent writes, web search, exports, or act tools. At the end, report focused test results, full pytest result, manual TUI smoke-test status, and any deviations from the plan.
```
