"""Tests for the natural language router."""

from __future__ import annotations

from pathlib import Path
import pytest

from core.action_executor import ActionExecutor
from core.academic.validators import CommandResult
from core.nl.intent import (
    INTENT_ADD_ASSIGNMENT,
    INTENT_ADD_CLASS,
    INTENT_ADD_NOTE,
    INTENT_ADD_SHIFT,
    INTENT_ARCHIVE_NOTE,
    INTENT_ASK_NOTES,
    INTENT_AVAILABILITY,
    INTENT_DEADLINES,
    INTENT_LIST_ASSIGNMENTS,
    INTENT_LIST_MODULES,
    INTENT_LIST_SHIFTS,
    INTENT_NOTE_ACTION,
    INTENT_PLAN,
    INTENT_REMINDERS,
    INTENT_SET_HOURS,
    INTENT_SET_STATUS,
    INTENT_STUDY,
    INTENT_TODAY,
    INTENT_UNKNOWN,
    INTENT_WEEK,
    IntentMatch,
)
from core.nl.router import ACTOR_PAYLOAD_KEY, NLProposalError, NLRouter
from core.policy_engine import PolicyDecision, PolicyEngine
from core.schemas import ActionOutcome, ActionProposal


def _make_router(db_path: Path) -> NLRouter:
    return NLRouter(
        db_path=db_path,
        timezone="Europe/Dublin",
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3.1:8b",
        ollama_timeout=30,
    )


def _confirm_and_execute(router: NLRouter, match: IntentMatch) -> str:
    proposal = router.build_write_proposal(match, actor_user_id=123)
    return router.execute_confirmed_write(proposal, actor_user_id=123)


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

    def test_fallback_with_query(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        monkeypatch.setattr(router, "_ask_notes", lambda slots: "searched notes")
        match = IntentMatch(intent=INTENT_UNKNOWN, confidence=0.0, slots={"query": "test query"})
        result = router.route_read(match)
        assert result == "searched notes"


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
        added = router._build_academic_service().add_assignment(
            title="ML Exam",
            due_at="2026-05-22 17:00",
        )
        match = IntentMatch(
            intent=INTENT_SET_STATUS,
            confidence=0.9,
            slots={"assignment_id_or_title": added.record_id or "", "status": "done"},
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

    def test_execute_write_refuses_direct_mutation(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Test Assignment", "due_at": "2026-06-01 23:59", "priority": "3"},
        )

        result = router.execute_write(match)

        assert "requires explicit confirmation" in result
        assignments = router._build_academic_service().list_all_assignments(include_completed=True)
        assert assignments == []

    def test_execute_confirmed_add_assignment(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Test Assignment", "due_at": "2026-06-01 23:59", "priority": "3"},
        )
        result = _confirm_and_execute(router, match)
        assert isinstance(result, str)

    def test_build_add_assignment_proposal_missing_title(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"due_at": "2026-06-01"},
        )
        with pytest.raises(NLProposalError, match="Missing assignment title"):
            router.build_write_proposal(match, actor_user_id=123)

    def test_build_add_assignment_proposal_invalid_due_rejects_without_mutation(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Bad date", "due_at": "someday maybe"},
        )

        with pytest.raises(NLProposalError, match="Invalid datetime"):
            router.build_write_proposal(match, actor_user_id=123)

        assignments = router._build_academic_service().list_all_assignments(include_completed=True)
        assert assignments == []

    def test_execute_set_status(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        add_match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Status Test", "due_at": "2026-06-01 23:59", "priority": "3"},
        )
        _confirm_and_execute(router, add_match)

        assignments = router._build_academic_service().list_all_assignments(include_completed=False)
        assert len(assignments) >= 1
        assignment_id = assignments[0].id

        status_match = IntentMatch(
            intent=INTENT_SET_STATUS,
            confidence=0.9,
            slots={"assignment_id_or_title": assignment_id, "status": "done"},
        )
        result = _confirm_and_execute(router, status_match)
        assert isinstance(result, str)

    def test_ambiguous_assignment_title_rejects_without_mutation(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        service = router._build_academic_service()
        service.add_assignment(title="Essay", due_at="2026-06-01 23:59")
        service.add_assignment(title="Essay", due_at="2026-06-02 23:59")
        match = IntentMatch(
            intent=INTENT_SET_STATUS,
            confidence=0.9,
            slots={"assignment_id_or_title": "Essay", "status": "done"},
        )

        with pytest.raises(NLProposalError, match="Multiple assignments"):
            router.build_write_proposal(match, actor_user_id=123)

        assignments = service.list_all_assignments(include_completed=True)
        assert [assignment.status.value for assignment in assignments] == ["todo", "todo"]

    def test_execute_add_note(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_NOTE,
            confidence=0.9,
            slots={"title": "Test Note", "content": "Some content here"},
        )
        result = _confirm_and_execute(router, match)
        assert isinstance(result, str)

    def test_execute_set_hours(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        added = router._build_academic_service().add_assignment(
            title="Hours Test",
            due_at="2026-06-01 23:59",
            estimated_hours=5,
        )
        match = IntentMatch(
            intent=INTENT_SET_HOURS,
            confidence=0.9,
            slots={"assignment_id_or_title": added.record_id or "", "completed_hours": "2.5"},
        )

        result = _confirm_and_execute(router, match)

        assert "Progress updated" in result

    def test_execute_add_class(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_CLASS,
            confidence=0.9,
            slots={"title": "NLP", "day": "mon", "start": "10:00", "end": "12:00"},
        )

        result = _confirm_and_execute(router, match)

        assert "Class added" in result

    def test_execute_add_shift(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_SHIFT,
            confidence=0.9,
            slots={
                "title": "Work",
                "start": "2026-06-01 16:00",
                "end": "2026-06-01 23:00",
            },
        )

        result = _confirm_and_execute(router, match)

        assert "Work shift added" in result

    def test_archive_note_is_destructive_proposal(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        note_result = router._build_knowledge_service().create_note(
            title="Archive me",
            body="Temporary note",
        )
        match = IntentMatch(
            intent=INTENT_ARCHIVE_NOTE,
            confidence=0.9,
            slots={"note_id": note_result.record_id or ""},
        )

        proposal = router.build_write_proposal(match, actor_user_id=123)

        assert proposal.approval_required is True
        assert proposal.criticality == "destructive"

    def test_build_write_proposal_is_unconfirmed_and_does_not_mutate(self, tmp_db: Path) -> None:
        router = _make_router(tmp_db)
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Deferred", "due_at": "2026-06-01 23:59", "priority": "3"},
        )

        proposal = router.build_write_proposal(match, actor_user_id=123)

        assert proposal.user_confirmed is False
        assert proposal.action_type == INTENT_ADD_ASSIGNMENT
        assert proposal.payload[ACTOR_PAYLOAD_KEY] == 123
        assignments = router._build_academic_service().list_all_assignments(include_completed=True)
        assert assignments == []

    def test_execute_confirmed_write_runs_policy_before_service(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        events: list[str] = []

        class RecordingPolicy(PolicyEngine):
            def check(self, proposal: ActionProposal) -> PolicyDecision:
                events.append("policy")
                return super().check(proposal)

        class FakeAcademicService:
            def add_assignment(self, **payload) -> CommandResult:
                events.append("write")
                return CommandResult(success=True, message="ok", record_id="abc")

        router = NLRouter(
            db_path=tmp_db,
            timezone="Europe/Dublin",
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3.1:8b",
            ollama_timeout=30,
            action_executor=ActionExecutor(policy_engine=RecordingPolicy()),
        )
        monkeypatch.setattr(router, "_build_academic_service", lambda: FakeAcademicService())
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Policy order", "due_at": "2026-06-01 23:59"},
        )
        proposal = router.build_write_proposal(match, actor_user_id=123)

        result = router.execute_confirmed_write(proposal, actor_user_id=123)

        assert result == "ok"
        assert events == ["policy", "write"]

    def test_execute_confirmed_write_blocks_service_when_policy_denies(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        events: list[str] = []

        class BlockingPolicy(PolicyEngine):
            def check(self, proposal: ActionProposal) -> PolicyDecision:
                events.append("policy")
                return PolicyDecision(
                    allowed=False,
                    outcome=ActionOutcome.BLOCKED,
                    reason="blocked by test policy",
                )

        class FakeAcademicService:
            def add_assignment(self, **payload) -> CommandResult:
                events.append("write")
                return CommandResult(success=True, message="should not run", record_id="abc")

        router = NLRouter(
            db_path=tmp_db,
            timezone="Europe/Dublin",
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3.1:8b",
            ollama_timeout=30,
            action_executor=ActionExecutor(policy_engine=BlockingPolicy()),
        )
        monkeypatch.setattr(router, "_build_academic_service", lambda: FakeAcademicService())
        match = IntentMatch(
            intent=INTENT_ADD_ASSIGNMENT,
            confidence=0.9,
            slots={"title": "Policy block", "due_at": "2026-06-01 23:59"},
        )
        proposal = router.build_write_proposal(match, actor_user_id=123)

        result = router.execute_confirmed_write(proposal, actor_user_id=123)

        assert result == "blocked by test policy"
        assert events == ["policy"]


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
