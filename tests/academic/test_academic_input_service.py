"""Tests for Phase 5 academic input service methods."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from core.academic.service import AcademicService
from core.db import init_db

TZ = ZoneInfo("Europe/Dublin")


@pytest.fixture
def service(tmp_path: Path) -> AcademicService:
    db_path = tmp_path / "data" / "atenas.sqlite"
    init_db(db_path)
    return AcademicService(db_path, timezone=TZ)


@pytest.fixture
def service_with_module(service: AcademicService) -> tuple[AcademicService, str]:
    result = service.add_module(name="Deep Learning", code="DL")
    assert result.success
    return service, result.record_id or ""


class TestAddModule:
    def test_create_module(self, service: AcademicService) -> None:
        result = service.add_module(name="Deep Learning", code="DL")
        assert result.success
        assert "Module added" in result.message

    def test_module_name_required(self, service: AcademicService) -> None:
        result = service.add_module(name="")
        assert not result.success
        assert "required" in result.message.lower()

    def test_module_name_too_long(self, service: AcademicService) -> None:
        result = service.add_module(name="a" * 201)
        assert not result.success

    def test_duplicate_module_skipped(self, service: AcademicService) -> None:
        service.add_module(name="Deep Learning", code="DL")
        result = service.add_module(name="Deep Learning", code="DL")
        assert not result.success
        assert "already exists" in result.message.lower()

    def test_module_with_optional_fields(self, service: AcademicService) -> None:
        result = service.add_module(
            name="NLP", code="NLP101", lecturer="Dr Smith", notes="Transformer module"
        )
        assert result.success
        modules = service.list_modules()
        assert len(modules) == 1
        assert modules[0].lecturer == "Dr Smith"


class TestAddClassSession:
    def test_create_class_session(self, service: AcademicService) -> None:
        result = service.add_class_session(
            title="Deep Learning", weekday=0, start_time="10:00", end_time="12:00"
        )
        assert result.success
        assert "Class added" in result.message

    def test_invalid_weekday(self, service: AcademicService) -> None:
        result = service.add_class_session(
            title="DL", weekday=7, start_time="10:00", end_time="12:00"
        )
        assert not result.success

    def test_start_before_end(self, service: AcademicService) -> None:
        result = service.add_class_session(
            title="DL", weekday=0, start_time="14:00", end_time="10:00"
        )
        assert not result.success

    def test_invalid_time_format(self, service: AcademicService) -> None:
        result = service.add_class_session(
            title="DL", weekday=0, start_time="10am", end_time="12:00"
        )
        assert not result.success

    def test_duplicate_class_skipped(self, service: AcademicService) -> None:
        service.add_class_session(
            title="DL", weekday=0, start_time="10:00", end_time="12:00"
        )
        result = service.add_class_session(
            title="DL", weekday=0, start_time="10:00", end_time="12:00"
        )
        assert not result.success
        assert "already exists" in result.message.lower()

    def test_with_module_id(self, service_with_module: tuple) -> None:
        service, module_id = service_with_module
        result = service.add_class_session(
            title="DL", weekday=1, start_time="10:00", end_time="12:00", module_id=module_id
        )
        assert result.success

    def test_invalid_module_id(self, service: AcademicService) -> None:
        result = service.add_class_session(
            title="DL", weekday=0, start_time="10:00", end_time="12:00", module_id="nonexistent"
        )
        assert not result.success
        assert "not found" in result.message.lower()


class TestAddWorkShift:
    def test_create_work_shift(self, service: AcademicService) -> None:
        result = service.add_work_shift(
            title="Work",
            start_at="2026-05-18 16:00",
            end_at="2026-05-18 23:00",
        )
        assert result.success

    def test_date_only_rejected(self, service: AcademicService) -> None:
        result = service.add_work_shift(
            title="Work",
            start_at="2026-05-18",
            end_at="2026-05-18 23:00",
        )
        assert not result.success
        assert "Date-only not allowed" in result.message

    def test_start_before_end(self, service: AcademicService) -> None:
        result = service.add_work_shift(
            title="Work",
            start_at="2026-05-18 23:00",
            end_at="2026-05-18 16:00",
        )
        assert not result.success

    def test_invalid_energy_cost(self, service: AcademicService) -> None:
        result = service.add_work_shift(
            title="Work",
            start_at="2026-05-18 16:00",
            end_at="2026-05-18 23:00",
            energy_cost=6,
        )
        assert not result.success

    def test_duplicate_shift_skipped(self, service: AcademicService) -> None:
        service.add_work_shift(
            title="Work",
            start_at="2026-05-18 16:00",
            end_at="2026-05-18 23:00",
        )
        result = service.add_work_shift(
            title="Work",
            start_at="2026-05-18 16:00",
            end_at="2026-05-18 23:00",
        )
        assert not result.success
        assert "already exists" in result.message.lower()

    def test_default_title(self, service: AcademicService) -> None:
        result = service.add_work_shift(
            title="",
            start_at="2026-05-18 16:00",
            end_at="2026-05-18 23:00",
        )
        assert result.success


class TestAddAssignment:
    def test_create_assignment(self, service: AcademicService) -> None:
        result = service.add_assignment(
            title="NLP CA1",
            due_at="2026-05-21 23:59",
        )
        assert result.success
        assert "Assignment added" in result.message

    def test_date_only_becomes_2359(self, service: AcademicService) -> None:
        result = service.add_assignment(
            title="Test",
            due_at="2026-05-21",
        )
        assert result.success
        assignments = service.list_all_assignments()
        assert len(assignments) == 1
        assert assignments[0].due_at.hour == 23
        assert assignments[0].due_at.minute == 59

    def test_title_required(self, service: AcademicService) -> None:
        result = service.add_assignment(title="", due_at="2026-05-21")
        assert not result.success
        assert "required" in result.message.lower()

    def test_invalid_priority(self, service: AcademicService) -> None:
        result = service.add_assignment(
            title="Test", due_at="2026-05-21", priority=6
        )
        assert not result.success

    def test_invalid_status(self, service: AcademicService) -> None:
        result = service.add_assignment(
            title="Test", due_at="2026-05-21", status="unknown"
        )
        assert not result.success

    def test_negative_hours_rejected(self, service: AcademicService) -> None:
        result = service.add_assignment(
            title="Test", due_at="2026-05-21", estimated_hours=-1
        )
        assert not result.success

    def test_duplicate_assignment_skipped(self, service: AcademicService) -> None:
        service.add_assignment(title="NLP CA1", due_at="2026-05-21 23:59")
        result = service.add_assignment(title="NLP CA1", due_at="2026-05-21 23:59")
        assert not result.success
        assert "already exists" in result.message.lower()

    def test_with_module_id(self, service_with_module: tuple) -> None:
        service, module_id = service_with_module
        result = service.add_assignment(
            title="DL Report", due_at="2026-05-25", module_id=module_id
        )
        assert result.success


class TestUpdateAssignmentStatus:
    def test_update_status(self, service: AcademicService) -> None:
        add_result = service.add_assignment(title="Test", due_at="2026-05-21")
        assert add_result.success
        assignment_id = add_result.record_id or ""

        result = service.update_assignment_status(assignment_id, "in_progress")
        assert result.success
        assert "in_progress" in result.message

    def test_invalid_status(self, service: AcademicService) -> None:
        add_result = service.add_assignment(title="Test", due_at="2026-05-21")
        assert add_result.success

        result = service.update_assignment_status(add_result.record_id or "", "invalid")
        assert not result.success

    def test_nonexistent_assignment(self, service: AcademicService) -> None:
        result = service.update_assignment_status("nonexistent-id", "done")
        assert not result.success
        assert "not found" in result.message.lower()


class TestUpdateCompletedHours:
    def test_update_hours(self, service: AcademicService) -> None:
        add_result = service.add_assignment(
            title="Test", due_at="2026-05-21", estimated_hours=10
        )
        assert add_result.success

        result = service.update_completed_hours(add_result.record_id or "", 3.5)
        assert result.success
        assert "3.5h" in result.message
        assert "Remaining: 6.5h" in result.message

    def test_negative_hours_rejected(self, service: AcademicService) -> None:
        add_result = service.add_assignment(title="Test", due_at="2026-05-21")
        assert add_result.success

        result = service.update_completed_hours(add_result.record_id or "", -1)
        assert not result.success

    def test_hours_can_exceed_estimate(self, service: AcademicService) -> None:
        add_result = service.add_assignment(
            title="Test", due_at="2026-05-21", estimated_hours=5
        )
        assert add_result.success

        result = service.update_completed_hours(add_result.record_id or "", 10)
        assert result.success

    def test_nonexistent_assignment(self, service: AcademicService) -> None:
        result = service.update_completed_hours("nonexistent-id", 2)
        assert not result.success
