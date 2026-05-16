"""Tests for Phase 5 CSV/JSON importers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from core.academic.importers import (
    import_assignments_csv,
    import_class_sessions_csv,
    import_json_bundle,
    import_modules_csv,
    import_work_shifts_csv,
)
from core.academic.service import AcademicService
from core.db import init_db


@pytest.fixture
def service(tmp_path: Path) -> AcademicService:
    db_path = tmp_path / "data" / "atenas.sqlite"
    init_db(db_path)
    return AcademicService(db_path)


@pytest.fixture
def assignments_csv(tmp_path: Path) -> Path:
    path = tmp_path / "assignments.csv"
    path.write_text(
        "title,module_id,due_at,priority,status,weight,estimated_hours,completed_hours,notes\n"
        "NLP CA1,,2026-05-21 23:59,2,todo,40,6,0,First coursework\n"
        "DL Report,,2026-05-25 23:59,1,in_progress,60,12,4,Main report\n"
    )
    return path


@pytest.fixture
def shifts_csv(tmp_path: Path) -> Path:
    path = tmp_path / "work_shifts.csv"
    path.write_text(
        "title,start_at,end_at,location,role,energy_cost,notes\n"
        "Work,2026-05-18 16:00,2026-05-18 23:00,Carluccio's,Chef,4,Dinner shift\n"
        "Work,2026-05-20 09:00,2026-05-20 17:00,Carluccio's,Chef,3,Day shift\n"
    )
    return path


@pytest.fixture
def modules_csv(tmp_path: Path) -> Path:
    path = tmp_path / "modules.csv"
    path.write_text(
        "name,code,lecturer,notes\n"
        "Deep Learning,DL,,Main MSc module\n"
        "Natural Language Processing,NLP,,Transformer-heavy module\n"
    )
    return path


@pytest.fixture
def classes_csv(tmp_path: Path) -> Path:
    path = tmp_path / "classes.csv"
    path.write_text(
        "title,module_id,weekday,start_time,end_time,location,notes\n"
        "Deep Learning,,mon,10:00,12:00,Room 101,\n"
        "NLP,,thu,12:00,14:00,Room 202,\n"
    )
    return path


class TestDryRun:
    def test_dry_run_assignments_creates_no_records(
        self, service: AcademicService, assignments_csv: Path
    ) -> None:
        result = import_assignments_csv(assignments_csv, service, dry_run=True)
        assert result.parsed == 2
        assert result.created == 2
        assert result.errors == 0
        assert len(service.list_all_assignments()) == 0

    def test_dry_run_shifts_creates_no_records(
        self, service: AcademicService, shifts_csv: Path
    ) -> None:
        result = import_work_shifts_csv(shifts_csv, service, dry_run=True)
        assert result.parsed == 2
        assert result.created == 2
        assert result.errors == 0
        assert len(service.list_all_work_shifts()) == 0


class TestAssignmentImport:
    def test_valid_csv_import(self, service: AcademicService, assignments_csv: Path) -> None:
        result = import_assignments_csv(assignments_csv, service, dry_run=False)
        assert result.parsed == 2
        assert result.created == 2
        assert result.errors == 0
        assert len(service.list_all_assignments()) == 2

    def test_invalid_rows_produce_errors(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(
            "title,due_at\n"
            "Good,2026-05-21 23:59\n"
            ",2026-05-21 23:59\n"
            "Bad Date,not-a-date\n"
        )
        result = import_assignments_csv(path, service, dry_run=False)
        assert result.errors == 2
        assert result.created == 1

    def test_missing_required_columns(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text("title,notes\nTest,some notes\n")
        result = import_assignments_csv(path, service, dry_run=False)
        assert result.errors == 1
        assert "due_at" in result.error_details[0]

    def test_duplicate_rows_skipped(self, service: AcademicService, assignments_csv: Path) -> None:
        import_assignments_csv(assignments_csv, service, dry_run=False)
        result = import_assignments_csv(assignments_csv, service, dry_run=False)
        assert result.skipped == 2
        assert result.created == 0


class TestWorkShiftImport:
    def test_valid_csv_import(self, service: AcademicService, shifts_csv: Path) -> None:
        result = import_work_shifts_csv(shifts_csv, service, dry_run=False)
        assert result.parsed == 2
        assert result.created == 2
        assert result.errors == 0
        assert len(service.list_all_work_shifts()) == 2

    def test_date_only_rejected(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(
            "title,start_at,end_at\n"
            "Work,2026-05-18,2026-05-18 23:00\n"
        )
        result = import_work_shifts_csv(path, service, dry_run=False)
        assert result.errors == 1

    def test_duplicate_shifts_skipped(self, service: AcademicService, shifts_csv: Path) -> None:
        import_work_shifts_csv(shifts_csv, service, dry_run=False)
        result = import_work_shifts_csv(shifts_csv, service, dry_run=False)
        assert result.skipped == 2


class TestModuleImport:
    def test_valid_csv_import(self, service: AcademicService, modules_csv: Path) -> None:
        result = import_modules_csv(modules_csv, service, dry_run=False)
        assert result.parsed == 2
        assert result.created == 2
        assert result.errors == 0
        assert len(service.list_modules()) == 2

    def test_duplicate_modules_skipped(self, service: AcademicService, modules_csv: Path) -> None:
        import_modules_csv(modules_csv, service, dry_run=False)
        result = import_modules_csv(modules_csv, service, dry_run=False)
        assert result.skipped == 2


class TestClassSessionImport:
    def test_valid_csv_import(self, service: AcademicService, classes_csv: Path) -> None:
        result = import_class_sessions_csv(classes_csv, service, dry_run=False)
        assert result.parsed == 2
        assert result.created == 2
        assert result.errors == 0
        assert len(service.list_class_sessions()) == 2

    def test_invalid_weekday(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(
            "title,weekday,start_time,end_time\n"
            "DL,invalid,10:00,12:00\n"
        )
        result = import_class_sessions_csv(path, service, dry_run=False)
        assert result.errors == 1

    def test_start_after_end(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(
            "title,weekday,start_time,end_time\n"
            "DL,mon,14:00,10:00\n"
        )
        result = import_class_sessions_csv(path, service, dry_run=False)
        assert result.errors == 1


class TestJsonBundleImport:
    def test_json_bundle_import(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bundle.json"
        path.write_text(
            """{
                "modules": [{"name": "DL", "code": "DL"}],
                "class_sessions": [{"title": "DL", "weekday": "mon", "start_time": "10:00", "end_time": "12:00"}],
                "work_shifts": [{"title": "Work", "start_at": "2026-05-18 16:00", "end_at": "2026-05-18 23:00"}],
                "assignments": [{"title": "CA1", "due_at": "2026-05-21 23:59"}]
            }"""
        )
        result = import_json_bundle(path, service, dry_run=False)
        assert result.errors == 0
        assert result.created == 4
        assert len(service.list_modules()) == 1
        assert len(service.list_class_sessions()) == 1
        assert len(service.list_all_work_shifts()) == 1
        assert len(service.list_all_assignments()) == 1

    def test_json_dry_run(self, service: AcademicService, tmp_path: Path) -> None:
        path = tmp_path / "bundle.json"
        path.write_text(
            """{
                "modules": [{"name": "DL"}],
                "assignments": [{"title": "CA1", "due_at": "2026-05-21"}]
            }"""
        )
        result = import_json_bundle(path, service, dry_run=True)
        assert result.created == 2
        assert len(service.list_modules()) == 0
        assert len(service.list_all_assignments()) == 0


class TestImportResultSummary:
    def test_summary_counts_correct(self, service: AcademicService, assignments_csv: Path) -> None:
        result = import_assignments_csv(assignments_csv, service, dry_run=False)
        assert result.parsed == result.created + result.errors + result.skipped
