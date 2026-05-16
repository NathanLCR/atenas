"""Dashboard tests for Phase 3 read-only schedule pages."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from core.academic.planner import (
    PlannedStudyBlock,
    StudyPlan,
    StudyPlanSummary,
    UnscheduledWorkload,
)
from core.academic.service import AcademicService
from core.skill_registry import SkillRegistry

TZ = ZoneInfo("Europe/Dublin")
MONDAY = date(2026, 5, 18)
SUNDAY = date(2026, 5, 24)


def test_dashboard_week_route_returns_200(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        service = AcademicService(settings.db_path, settings.timezone)
        service.create_class_session("Demo Lecture", 0, "10:00", "12:00")

        response = client.get("/dashboard/week")

    assert response.status_code == 200
    assert "Weekly Schedule" in response.text
    assert "Demo Lecture" in response.text


def test_dashboard_deadlines_route_returns_200(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        service = AcademicService(settings.db_path, settings.timezone)
        service.create_assignment(
            "Demo Essay",
            datetime(2026, 5, 21, 17, 0, tzinfo=TZ),
            priority=2,
        )

        response = client.get("/dashboard/deadlines")

    assert response.status_code == 200
    assert "Deadlines" in response.text
    assert "Demo Essay" in response.text
    assert "todo" in response.text


def test_dashboard_plan_route_returns_200(settings: Settings) -> None:
    fake_service = _FakePlanningService(_dashboard_plan(blocks=[_dashboard_block()]))
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client, patch("app.dashboard._get_academic_service", return_value=fake_service):
        response = client.get("/dashboard/plan")

    assert response.status_code == 200
    assert "Study Plan" in response.text
    assert "18 May" in response.text
    assert "24 May" in response.text
    assert "NLP CA1" in response.text


def test_dashboard_plan_empty_state(settings: Settings) -> None:
    fake_service = _FakePlanningService(_dashboard_plan(blocks=[], required=0, planned=0))
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client, patch("app.dashboard._get_academic_service", return_value=fake_service):
        response = client.get("/dashboard/plan")

    assert response.status_code == 200
    assert "No open assignments to plan." in response.text


def test_dashboard_plan_warning_rendering(settings: Settings) -> None:
    plan = _dashboard_plan(
        blocks=[],
        required=120,
        planned=0,
        unscheduled_minutes=120,
        unscheduled=[_dashboard_unscheduled()],
        unestimated=["Needs estimate"],
    )
    fake_service = _FakePlanningService(plan)
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client, patch("app.dashboard._get_academic_service", return_value=fake_service):
        response = client.get("/dashboard/plan")

    assert response.status_code == 200
    assert "Warnings" in response.text
    assert "unscheduled before deadline" in response.text
    assert "assignments need estimated hours" in response.text


def _dashboard_plan(
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


def _dashboard_block() -> PlannedStudyBlock:
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


def _dashboard_unscheduled() -> UnscheduledWorkload:
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
    def __init__(self, plan: StudyPlan) -> None:
        self.plan = plan

    def get_study_plan(self) -> StudyPlan:
        return self.plan
