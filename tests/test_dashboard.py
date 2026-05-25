"""Tests for the Phase 2 read-only dashboard."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from core.db import get_connection
from core.skill_registry import SkillRegistry


def test_home_route_returns_200(settings: Settings) -> None:
    """Dashboard home should render with the app name."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/")

    assert response.status_code == 200
    assert settings.app_name in response.text


def test_home_route_renders_cockpit_overview_from_local_data(settings: Settings) -> None:
    """Dashboard home should render the read-only cockpit overview."""

    app = create_app(settings=settings, registry=SkillRegistry())
    fake_service = _FakeDashboardAcademicService()

    with (
        TestClient(app) as client,
        patch("app.dashboard._get_academic_service", return_value=fake_service),
        patch(
            "app.dashboard._load_trace_records",
            return_value=[
                {
                    "status": "success",
                    "model": "llama3.1:8b",
                    "tool_call_count": 1,
                    "user_message_summary": "generate_study_plan",
                }
            ],
        ),
        patch(
            "app.dashboard._load_llm_call_records",
            return_value=[{"success": 1, "latency_ms": 120, "model": "llama3.1:8b"}],
        ),
    ):
        response = client.get("/dashboard/")

    assert response.status_code == 200
    assert "Local-Only" in response.text
    assert "Study Orchestrator" in response.text
    assert "Today&#39;s Summary" in response.text
    assert "Dissertation reading" in response.text
    assert "NLP CA1" in response.text
    assert "System Health" in response.text
    assert "Weekly Capacity" in response.text
    assert "System Status" in response.text


def test_dashboard_shell_does_not_render_mutating_controls(settings: Settings) -> None:
    """The local dashboard should not expose write-like cockpit controls."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        responses = [
            client.get("/dashboard/"),
            client.get("/dashboard/week"),
            client.get("/dashboard/plan"),
            client.get("/dashboard/retrieval"),
            client.get("/dashboard/traces"),
        ]

    joined = "\n".join(response.text for response in responses)
    for forbidden in ("Add Event", "Regenerate", "Clear", "Export CSV", "Adjust Constraints"):
        assert forbidden not in joined


def test_logs_route_returns_200(settings: Settings) -> None:
    """Dashboard logs should render even when no records exist."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/logs")

    assert response.status_code == 200


def test_logs_route_empty_state(settings: Settings) -> None:
    """An empty llm_calls table should show the empty state."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_calls (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    estimated_cost REAL,
                    success INTEGER NOT NULL,
                    latency_ms INTEGER,
                    schema_valid INTEGER,
                    policy_passed INTEGER,
                    outcome TEXT NOT NULL DEFAULT 'success',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/logs")

    assert response.status_code == 200
    assert "No LLM calls recorded yet." in response.text


def test_traces_route_returns_200(settings: Settings) -> None:
    """Dashboard traces should render even when no traces exist."""
    from app.main import create_app
    from core.skill_registry import SkillRegistry

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/traces")

    assert response.status_code == 200


def test_traces_route_empty_state(settings: Settings) -> None:
    """Empty agent_traces table should show the empty state."""
    from app.main import create_app
    from core.db import get_connection
    from core.skill_registry import SkillRegistry

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id TEXT PRIMARY KEY,
                    actor_user_id INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    model TEXT,
                    status TEXT NOT NULL,
                    user_message_summary TEXT NOT NULL,
                    final_message_summary TEXT,
                    tool_call_count INTEGER NOT NULL DEFAULT 0,
                    pending_action_type TEXT,
                    latency_ms INTEGER,
                    error TEXT
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/traces")

    assert response.status_code == 200
    assert "No agent traces recorded yet." in response.text


def test_traces_route_shows_stored_traces(settings: Settings) -> None:
    """Dashboard traces should display stored trace records."""
    from app.main import create_app
    from core.db import get_connection
    from core.skill_registry import SkillRegistry
    from core.schemas import new_id

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id TEXT PRIMARY KEY,
                    actor_user_id INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    model TEXT,
                    status TEXT NOT NULL,
                    user_message_summary TEXT NOT NULL,
                    final_message_summary TEXT,
                    tool_call_count INTEGER NOT NULL DEFAULT 0,
                    pending_action_type TEXT,
                    latency_ms INTEGER,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO agent_traces
                    (id, actor_user_id, started_at, model, status,
                     user_message_summary, final_message_summary, tool_call_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (new_id(), 123, "2026-05-24T10:00:00", "llama3.1:8b",
                 "success", "mark my essay done", "Done!", 1),
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/traces")

    assert response.status_code == 200
    assert "mark my essay done" in response.text
    assert "success" in response.text


def test_traces_route_renders_stdout_summary_from_trace_records(settings: Settings) -> None:
    """Agent traces should include a read-only stdout-style summary panel."""
    from app.main import create_app
    from core.db import get_connection
    from core.schemas import new_id
    from core.skill_registry import SkillRegistry

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id TEXT PRIMARY KEY,
                    actor_user_id INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    model TEXT,
                    status TEXT NOT NULL,
                    user_message_summary TEXT NOT NULL,
                    final_message_summary TEXT,
                    tool_call_count INTEGER NOT NULL DEFAULT 0,
                    pending_action_type TEXT,
                    latency_ms INTEGER,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO agent_traces
                    (id, actor_user_id, started_at, model, status,
                     user_message_summary, final_message_summary, tool_call_count,
                     latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(),
                    123,
                    "2026-05-24T10:00:00",
                    "llama3.1:8b",
                    "success",
                    "generate_study_plan",
                    "Done!",
                    2,
                    450,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/traces")

    assert response.status_code == 200
    assert "System StdOut" in response.text
    assert "[INFO]" in response.text
    assert "generate_study_plan" in response.text
    assert "tools=2" in response.text


TZ = ZoneInfo("Europe/Dublin")


def _fake_block(
    title: str,
    start: datetime,
    end: datetime,
    *,
    kind: str = "class",
    metadata: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        start_at=start,
        end_at=end,
        kind=kind,
        metadata=metadata or {},
    )


class _FakeDashboardAcademicService:
    def __init__(self) -> None:
        self.today = date(2026, 5, 25)
        self.assignment = SimpleNamespace(
            id="asg-1",
            title="NLP CA1",
            due_at=datetime(2026, 5, 27, 17, 0, tzinfo=TZ),
            priority=1,
            status=SimpleNamespace(value="todo"),
            estimated_hours=4,
            completed_hours=1,
        )
        self.study_block = SimpleNamespace(
            assignment_id="asg-1",
            assignment_title="Dissertation reading",
            module_name="Dissertation",
            start_at=datetime(2026, 5, 25, 9, 30, tzinfo=TZ),
            end_at=datetime(2026, 5, 25, 10, 30, tzinfo=TZ),
            minutes=60,
            due_at=datetime(2026, 5, 27, 17, 0, tzinfo=TZ),
            priority=1,
            reason="low-intensity reading before a late shift",
            intensity="light",
        )

    def get_today_overview(self) -> SimpleNamespace:
        return SimpleNamespace(
            date=self.today,
            classes=[
                _fake_block(
                    "NLP Class",
                    datetime(2026, 5, 25, 9, 0, tzinfo=TZ),
                    datetime(2026, 5, 25, 11, 0, tzinfo=TZ),
                    kind="class",
                )
            ],
            work_shifts=[
                _fake_block(
                    "Six by Nico",
                    datetime(2026, 5, 25, 16, 0, tzinfo=TZ),
                    datetime(2026, 5, 25, 23, 0, tzinfo=TZ),
                    kind="work",
                    metadata={"fatigue_level": "high"},
                )
            ],
            deadlines=[self.assignment],
            availability=SimpleNamespace(
                study_windows=[
                    SimpleNamespace(
                        start_at=datetime(2026, 5, 25, 11, 15, tzinfo=TZ),
                        end_at=datetime(2026, 5, 25, 12, 45, tzinfo=TZ),
                        minutes=90,
                        max_intensity="light",
                    )
                ],
                total_study_minutes=90,
            ),
        )

    def get_study_plan(self) -> SimpleNamespace:
        return SimpleNamespace(
            blocks=[self.study_block],
            summary=SimpleNamespace(
                total_available_minutes=240,
                total_required_minutes=240,
                total_planned_minutes=60,
                total_unscheduled_minutes=180,
                unestimated_assignments=[],
                overdue_assignments=[],
            ),
        )

    def get_week_overview(self) -> SimpleNamespace:
        day_summary = SimpleNamespace(
            date=self.today,
            class_minutes=120,
            work_minutes=420,
            study_minutes=90,
        )
        return SimpleNamespace(
            start_date=self.today,
            end_date=date(2026, 5, 31),
            class_count=1,
            work_shift_count=1,
            open_deadline_count=1,
            availability=SimpleNamespace(total_study_minutes=90, days=[]),
            day_summaries=[day_summary],
        )

    def list_upcoming_assignments(self, limit: int = 10, include_completed: bool = False) -> list[SimpleNamespace]:
        return [self.assignment]
