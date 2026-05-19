"""Tests for the natural language router."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.nl.intent import (
    INTENT_ADD_ASSIGNMENT,
    INTENT_ADD_NOTE,
    INTENT_ASK_NOTES,
    INTENT_AVAILABILITY,
    INTENT_DEADLINES,
    INTENT_LIST_ASSIGNMENTS,
    INTENT_LIST_MODULES,
    INTENT_LIST_SHIFTS,
    INTENT_NOTE_ACTION,
    INTENT_PLAN,
    INTENT_REMINDERS,
    INTENT_SET_STATUS,
    INTENT_STUDY,
    INTENT_TODAY,
    INTENT_UNKNOWN,
    INTENT_WEEK,
    IntentMatch,
)
from core.nl.router import NLRouter


def _make_router(db_path: Path) -> NLRouter:
    return NLRouter(
        db_path=db_path,
        timezone="Europe/Dublin",
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3.1:8b",
        ollama_timeout=30,
    )


class TestNLRouterReadIntents:
    def test_today_routes_to_today(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_TODAY, confidence=0.9, slots={})
        result = router.route_read(match)
        assert "Today" in result

    def test_week_routes_to_week(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_WEEK, confidence=0.9, slots={})
        result = router.route_read(match)
        assert "Week" in result

    def test_deadlines_routes_to_deadlines(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_DEADLINES, confidence=0.9, slots={})
        result = router.route_read(match)
        assert isinstance(result, str)

    def test_availability_routes_to_availability(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_AVAILABILITY, confidence=0.9, slots={})
        result = router.route_read(match)
        assert "Availability" in result

    def test_plan_routes_to_plan(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_PLAN, confidence=0.9, slots={})
        result = router.route_read(match)
        assert isinstance(result, str)

    def test_study_routes_to_study(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_STUDY, confidence=0.9, slots={})
        result = router.route_read(match)
        assert isinstance(result, str)

    def test_list_assignments_routes(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_LIST_ASSIGNMENTS, confidence=0.9, slots={})
        result = router.route_read(match)
        assert isinstance(result, str)

    def test_list_modules_routes(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_LIST_MODULES, confidence=0.9, slots={})
        result = router.route_read(match)
        assert isinstance(result, str)

    def test_list_shifts_routes(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_LIST_SHIFTS, confidence=0.9, slots={})
        result = router.route_read(match)
        assert isinstance(result, str)

    def test_reminders_routes(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_REMINDERS, confidence=0.9, slots={})
        result = router.route_read(match)
        assert "Reminders" in result

    def test_note_action_without_note_id(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_NOTE_ACTION, confidence=0.9, slots={"action": "summarize"})
        result = router.route_read(match)
        assert "Which note" in result

    def test_note_action_with_invalid_id(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_NOTE_ACTION, confidence=0.9, slots={"note_id": "abc", "action": "summarize"})
        result = router.route_read(match)
        assert "Invalid note ID" in result

    def test_ask_notes_without_query(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_ASK_NOTES, confidence=0.9, slots={})
        result = router.route_read(match)
        assert "What would you like to search" in result

    def test_fallback_with_query(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_UNKNOWN, confidence=0.0, slots={"query": "test query"})
        result = router.route_read(match)
        assert isinstance(result, str)


class TestNLRouterWriteIntents:
    def test_confirm_add_assignment(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "ML Exam", "due_at": "2026-05-22 17:00", "priority": "5"},
        )
        result = router.build_confirmation(match)
        assert "Add assignment?" in result
        assert "ML Exam" in result
        assert "yes" in result.lower()

    def test_confirm_set_status(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_SET_STATUS,
            confidence=0.9,
            slots={"assignment_id_or_title": "ML Exam", "status": "done"},
        )
        result = router.build_confirmation(match)
        assert "Update assignment status?" in result
        assert "ML Exam" in result

    def test_confirm_add_note(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_NOTE,
            confidence=0.9,
            slots={"title": "CNN Notes", "content": "CNNs are neural networks..."},
        )
        result = router.build_confirmation(match)
        assert "Add note?" in result
        assert "CNN Notes" in result

    def test_execute_add_assignment(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Test Assignment", "due_at": "2026-06-01 23:59", "priority": "3"},
        )
        result = router.execute_write(match)
        assert isinstance(result, str)

    def test_execute_add_assignment_missing_title(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"due_at": "2026-06-01"},
        )
        result = router.execute_write(match)
        assert "Missing title" in result

    def test_execute_set_status(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        add_match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Status Test", "due_at": "2026-06-01 23:59", "priority": "3"},
        )
        router.execute_write(add_match)

        assignments = router._build_academic_service().list_all_assignments(include_completed=False)
        assert len(assignments) >= 1
        assignment_id = assignments[0].id

        status_match = IntentMatch(
            intent=INTENT_SET_STATUS,
            confidence=0.9,
            slots={"assignment_id_or_title": assignment_id, "status": "done"},
        )
        result = router.execute_write(status_match)
        assert isinstance(result, str)

    def test_execute_add_note(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_NOTE,
            confidence=0.9,
            slots={"title": "Test Note", "content": "Some content here"},
        )
        result = router.execute_write(match)
        assert isinstance(result, str)


class TestNLRouterSuggestions:
    def test_suggest_command_for_known_intent(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent=INTENT_ASK_NOTES, confidence=0.5, slots={"query": "hello"})
        result = router.suggest_command(match)
        assert "/ask_notes" in result

    def test_suggest_command_for_unknown_intent(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(intent="nonexistent", confidence=0.3, slots={})
        result = router.suggest_command(match)
        assert "/ask_notes" in result
