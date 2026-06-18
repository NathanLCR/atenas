"""WP2 acceptance tests: tool result curation, pagination, limits, and verbosity."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pytest

from core.academic.models import StudyModule, Assignment, ClassSession, WorkShift
from core.knowledge.models import Note
from core.nl.tools import ToolRegistry


def test_list_modules_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    academic = registry._academic()

    # Empty state check
    run = registry.run_tool("list_modules", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "No modules" in run.result.message
    assert run.result.data["total"] == 0
    assert run.result.data["modules"] == []

    # Insert test modules
    for i in range(12):
        academic.repository.create_module(
            StudyModule(name=f"Module {i}", code=f"MOD{i:02d}", lecturer=f"Lecturer {i}")
        )

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("list_modules", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 modules" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["modules"]) == 10
    # Concise checks: name + code, no lecturer
    assert "lecturer" not in run.result.data["modules"][0]
    assert run.result.data["modules"][0]["name"] == "Module 0"
    assert run.result.data["modules"][0]["code"] == "MOD00"

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool("list_modules", {"limit": 2, "offset": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 3–4 of 12 modules" in run.result.message
    assert len(run.result.data["modules"]) == 2
    assert run.result.data["modules"][0]["name"] == "Module 2"

    # Detailed verbosity
    run = registry.run_tool("list_modules", {"verbosity": "detailed", "limit": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert len(run.result.data["modules"]) == 2
    assert "lecturer" in run.result.data["modules"][0]
    assert run.result.data["modules"][0]["lecturer"] == "Lecturer 0"


def test_list_assignments_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    academic = registry._academic()

    # Empty state check
    run = registry.run_tool("list_assignments", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "No matching assignments" in run.result.message
    assert run.result.data["total"] == 0
    assert run.result.data["assignments"] == []

    # Insert test assignments
    for i in range(12):
        academic.repository.create_assignment(
            Assignment(title=f"Assignment {i}", due_at=datetime(2026, 6, 1 + i, 12, 0), estimated_hours=5.0)
        )

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("list_assignments", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 assignments" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["assignments"]) == 10
    # Concise checks: title + due_at + status, no estimated_hours
    assert "estimated_hours" not in run.result.data["assignments"][0]
    assert run.result.data["assignments"][0]["title"] == "Assignment 0"

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool("list_assignments", {"limit": 2, "offset": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 3–4 of 12 assignments" in run.result.message
    assert len(run.result.data["assignments"]) == 2
    assert run.result.data["assignments"][0]["title"] == "Assignment 2"

    # Detailed verbosity
    run = registry.run_tool("list_assignments", {"verbosity": "detailed", "limit": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert len(run.result.data["assignments"]) == 2
    assert "estimated_hours" in run.result.data["assignments"][0]
    assert run.result.data["assignments"][0]["estimated_hours"] == 5.0


def test_list_class_sessions_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    academic = registry._academic()

    # Empty state check
    run = registry.run_tool("list_class_sessions", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "No class sessions" in run.result.message
    assert run.result.data["total"] == 0
    assert run.result.data["sessions"] == []

    # Insert test class sessions
    for i in range(12):
        academic.repository.create_class_session(
            ClassSession(title=f"Class {i}", weekday=0, start_time=f"{i:02d}:00", end_time=f"{i:02d}:50", notes=f"Note {i}")
        )

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("list_class_sessions", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 class sessions" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["sessions"]) == 10
    # Concise checks: title + weekday + times, no notes
    assert "notes" not in run.result.data["sessions"][0]
    assert run.result.data["sessions"][0]["title"] == "Class 0"

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool("list_class_sessions", {"limit": 2, "offset": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 3–4 of 12 class sessions" in run.result.message
    assert len(run.result.data["sessions"]) == 2
    assert run.result.data["sessions"][0]["title"] == "Class 2"

    # Detailed verbosity
    run = registry.run_tool("list_class_sessions", {"verbosity": "detailed", "limit": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert len(run.result.data["sessions"]) == 2
    assert "notes" in run.result.data["sessions"][0]
    assert run.result.data["sessions"][0]["notes"] == "Note 0"


def test_list_work_shifts_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    academic = registry._academic()

    # Empty state check
    run = registry.run_tool("list_work_shifts", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "No work shifts" in run.result.message
    assert run.result.data["total"] == 0
    assert run.result.data["shifts"] == []

    # Insert test work shifts
    for i in range(12):
        academic.repository.create_work_shift(
            WorkShift(
                title=f"Shift {i}",
                start_at=datetime(2026, 6, 1 + i, 14, 0),
                end_at=datetime(2026, 6, 1 + i, 22, 0),
                notes=f"Note {i}",
            )
        )

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("list_work_shifts", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 work shifts" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["shifts"]) == 10
    # Concise checks: title + times, no notes
    assert "notes" not in run.result.data["shifts"][0]
    assert run.result.data["shifts"][0]["title"] == "Shift 0"

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool("list_work_shifts", {"limit": 2, "offset": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 3–4 of 12 work shifts" in run.result.message
    assert len(run.result.data["shifts"]) == 2
    assert run.result.data["shifts"][0]["title"] == "Shift 2"

    # Detailed verbosity
    run = registry.run_tool("list_work_shifts", {"verbosity": "detailed", "limit": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert len(run.result.data["shifts"]) == 2
    assert "notes" in run.result.data["shifts"][0]
    assert run.result.data["shifts"][0]["notes"] == "Note 0"


def test_search_notes_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    knowledge = registry._knowledge()

    # Empty state check
    run = registry.run_tool("search_notes", {"query": "python"}, actor_user_id=None)
    # The search service returns an error when no notes are found, which makes the tool run ok=False
    assert run.result.ok is False
    assert "No notes or files found" in run.result.message
    assert run.result.data["results"] == []

    # Insert test notes
    for i in range(12):
        knowledge.repository.create_note(
            Note(title=f"Python study note {i}", body=f"We discuss Python concepts here for index {i}")
        )

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("search_notes", {"query": "python"}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 local result(s)" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["results"]) == 10
    # Concise checks: kind + id + title + snippet, no rank
    assert "rank" not in run.result.data["results"][0]
    assert "Python study note" in run.result.data["results"][0]["title"]

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool("search_notes", {"query": "python", "limit": 2, "offset": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 3–4 of 12 local result(s)" in run.result.message
    assert len(run.result.data["results"]) == 2

    # Detailed verbosity
    run = registry.run_tool(
        "search_notes", {"query": "python", "verbosity": "detailed", "limit": 2}, actor_user_id=None
    )
    assert run.result.ok is True
    assert len(run.result.data["results"]) == 2
    assert "rank" in run.result.data["results"][0]


def test_retrieve_sources_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    knowledge = registry._knowledge()

    # Empty state check
    run = registry.run_tool("retrieve_sources", {"question": "attention"}, actor_user_id=None)
    assert run.result.ok is True
    assert "No local sources found" in run.result.message
    assert run.result.data["sources"] == []

    # Insert test notes to be indexed for retrieval
    for i in range(12):
        knowledge.repository.create_note(
            Note(title=f"Transformer theory {i}", body=f"Attention mechanisms are interesting in step {i}")
        )

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("retrieve_sources", {"question": "attention"}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 local source(s)" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["sources"]) == 10
    # Concise checks: source_kind + source_id + title + snippet, no score
    assert "score" not in run.result.data["sources"][0]
    assert "Transformer theory" in run.result.data["sources"][0]["title"]

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool(
        "retrieve_sources", {"question": "attention", "limit": 2, "offset": 2}, actor_user_id=None
    )
    assert run.result.ok is True
    assert "Showing 3–4 of 12 local source(s)" in run.result.message
    assert len(run.result.data["sources"]) == 2

    # Detailed verbosity
    run = registry.run_tool(
        "retrieve_sources", {"question": "attention", "verbosity": "detailed", "limit": 2}, actor_user_id=None
    )
    assert run.result.ok is True
    assert len(run.result.data["sources"]) == 2
    assert "score" in run.result.data["sources"][0]


def test_detect_duplicate_modules_curation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    academic = registry._academic()

    # Empty state check
    run = registry.run_tool("detect_duplicate_modules", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "No duplicate modules" in run.result.message
    assert run.result.data["total"] == 0
    assert run.result.data["groups"] == []

    # Insert test duplicate groups
    for i in range(12):
        # Create duplicate pairs
        academic.repository.create_module(StudyModule(name=f"Duplicate Module {i}", code=f"MOD{i:02d}"))
        academic.repository.create_module(StudyModule(name=f"Duplicate Module {i}", code=f"MOD{i:02d}"))

    # Default call (limit=10, offset=0, verbosity="concise")
    run = registry.run_tool("detect_duplicate_modules", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 1–10 of 12 duplicate module group(s)" in run.result.message
    assert "Use offset=10 to see more" in run.result.message
    assert run.result.data["total"] == 12
    assert run.result.data["truncated"] is True
    assert len(run.result.data["groups"]) == 10
    # Concise checks: key + canonical_module + duplicate_modules, no all_modules
    assert "all_modules" not in run.result.data["groups"][0]
    assert run.result.data["groups"][0]["canonical_module"]["name"] == "Duplicate Module 0"

    # Custom pagination: limit=2, offset=2
    run = registry.run_tool("detect_duplicate_modules", {"limit": 2, "offset": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert "Showing 3–4 of 12 duplicate module group(s)" in run.result.message
    assert len(run.result.data["groups"]) == 2

    # Detailed verbosity
    run = registry.run_tool("detect_duplicate_modules", {"verbosity": "detailed", "limit": 2}, actor_user_id=None)
    assert run.result.ok is True
    assert len(run.result.data["groups"]) == 2
    assert "all_modules" in run.result.data["groups"][0]


def test_validation_steering_errors(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)

    # Test negative limit
    run = registry.run_tool("list_modules", {"limit": -1}, actor_user_id=None)
    assert run.result.ok is False
    assert "Invalid arguments" in run.result.message

    # Test negative offset
    run = registry.run_tool("list_modules", {"offset": -5}, actor_user_id=None)
    assert run.result.ok is False
    assert "Invalid arguments" in run.result.message

    # Test invalid verbosity
    run = registry.run_tool("list_modules", {"verbosity": "super_detailed"}, actor_user_id=None)
    assert run.result.ok is False
    assert "Invalid arguments" in run.result.message
