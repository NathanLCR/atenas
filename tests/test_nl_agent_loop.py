"""Tests for the tool-calling NL agent loop."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

from core.academic.models import AssignmentStatus
from core.academic.service import AcademicService
from core.llm.client import OllamaResponse
from core.nl.agent import AgentLoop
from core.nl.tools import ToolRegistry


class FakeToolClient:
    """Minimal mocked Ollama client for agent-loop tests."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = [json.dumps(response) for response in responses]
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> OllamaResponse:
        self.prompts.append(prompt)
        if not self.responses:
            return OllamaResponse(text=json.dumps({"type": "final", "message": "done"}), model="test")
        return OllamaResponse(text=self.responses.pop(0), model="test")


def test_delete_duplicate_modules_requires_confirmation_then_audits(
    tmp_db: Path,
    caplog,
) -> None:
    service = AcademicService(tmp_db)
    keep = service.create_module(name="Machine Learning", code="ML")
    delete = service.create_module(name="Machine Learning", code="ML")
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
        {
            "type": "tool_call",
            "tool_name": "deduplicate_modules",
            "arguments": {
                "groups": [
                    {
                        "canonical_module_id": keep.id,
                        "duplicate_module_ids": [delete.id],
                    }
                ]
            },
        },
    ])
    agent = AgentLoop(registry=registry, client=client)

    result = agent.run("delete my duplicate modules", actor_user_id=123)

    assert result.pending_action is not None
    assert "Delete duplicate modules?" in result.message
    assert keep.name in result.message
    assert delete.id[:8] in result.message
    assert len(service.list_modules()) == 2

    caplog.set_level(logging.INFO, logger="core.action_executor")
    executed = registry.execute_pending(result.pending_action, actor_user_id=123)

    assert executed.ok is True
    remaining = service.list_modules()
    assert [module.id for module in remaining] == [keep.id]
    audit = [record for record in caplog.records if record.message == "action_executed"][-1]
    assert audit.action_type == "deduplicate_modules"
    assert audit.actor_user_id == 123
    assert audit.policy_allowed is True
    assert audit.outcome == "success"


def test_auto_tier_assignment_status_executes_without_confirmation(
    tmp_db: Path,
    caplog,
) -> None:
    service = AcademicService(tmp_db)
    added = service.add_assignment(title="ML essay", due_at="2026-06-01 23:59")
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "set_assignment_status",
            "arguments": {"assignment": "ML essay", "status": "done"},
        },
        {"type": "final", "message": "Marked ML essay as done."},
    ])
    agent = AgentLoop(registry=registry, client=client)
    caplog.set_level(logging.INFO, logger="core.action_executor")

    result = agent.run("mark my ML essay done", actor_user_id=123)

    assert result.pending_action is None
    assert result.message == "Marked ML essay as done."
    assignment = service.repository.get_assignment_by_id(added.record_id or "")
    assert assignment is not None
    assert assignment.status == AssignmentStatus.DONE
    audit = [record for record in caplog.records if record.message == "action_executed"][-1]
    assert audit.action_type == "set_assignment_status"
    assert audit.actor_user_id == 123
    assert audit.policy_allowed is True
    assert audit.user_confirmed is False


def test_followup_uses_conversation_context_for_same_goal(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {"type": "final", "message": "Review CNN notes next."},
        {"type": "final", "message": "Great, let's review CNN notes."},
    ])
    agent = AgentLoop(registry=registry, client=client)

    first = agent.run("what should I study next?", actor_user_id=123)
    second = agent.run(
        "let's review that",
        conversation=first.conversation,
        actor_user_id=123,
    )

    assert second.message == "Great, let's review CNN notes."
    assert "Review CNN notes next." in client.prompts[1]
    assert "let's review that" in client.prompts[1]


def test_archive_note_requires_confirmation_then_executes(
    tmp_db: Path,
    caplog,
) -> None:
    academic = AcademicService(tmp_db)
    module = academic.create_module(name="Test Module")
    registry = ToolRegistry(tmp_db)
    knowledge = registry._knowledge()
    note_result = knowledge.create_note(
        title="Important Notes",
        body="Study material here",
        module_id=module.id,
    )
    note_id = int(note_result.record_id)

    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "archive_note",
            "arguments": {"note": str(note_id)},
        },
    ])
    agent = AgentLoop(registry=registry, client=client)

    result = agent.run("archive my Important Notes", actor_user_id=123)

    assert result.pending_action is not None
    assert "Archive note" in result.message
    assert "Important Notes" in result.message

    note = knowledge.get_note(note_id)
    assert note.archived is False

    caplog.set_level(logging.INFO, logger="core.action_executor")
    executed = registry.execute_pending(result.pending_action, actor_user_id=123)

    assert executed.ok is True
    note = knowledge.get_note(note_id)
    assert note.archived is True
    audit = [r for r in caplog.records if r.message == "action_executed"][-1]
    assert audit.action_type == "archive_note"
    assert audit.actor_user_id == 123
    assert audit.policy_allowed is True
    assert hasattr(audit, "before_state")
    assert hasattr(audit, "after_state")


def test_audit_before_after_on_delete_modules(tmp_db: Path, caplog) -> None:
    service = AcademicService(tmp_db)
    mod = service.create_module(name="ToDelete", code="DEL")
    registry = ToolRegistry(tmp_db)

    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "delete_modules",
            "arguments": {"module_ids": [mod.id]},
        },
    ])
    agent = AgentLoop(registry=registry, client=client)

    result = agent.run("delete the ToDelete module", actor_user_id=456)

    assert result.pending_action is not None
    caplog.set_level(logging.INFO, logger="core.action_executor")
    executed = registry.execute_pending(result.pending_action, actor_user_id=456)

    assert executed.ok is True
    audit = [r for r in caplog.records if r.message == "action_executed"][-1]
    assert audit.action_type == "delete_modules"
    assert hasattr(audit, "before_state")
    assert hasattr(audit, "after_state")
    assert audit.before_state is not None
    assert audit.after_state is not None


def test_web_tool_disabled_by_default(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=False)
    tool_names = [t.name for t in registry.list_tools()]
    assert "web_search" not in tool_names


def test_web_tool_enabled_when_flag_set(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    tool_names = [t.name for t in registry.list_tools()]
    assert "web_search" in tool_names


def test_web_search_returns_results(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    mock_response = json.dumps([
        "Test Query",
        ["Result 1", "Result 2"],
        ["Snippet 1", "Snippet 2"],
        ["http://example.com/1", "http://example.com/2"],
    ]).encode("utf-8")

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = patch("urllib.request.Request")
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda s, *a: None
        mock_urlopen.return_value.read = lambda: mock_response

        run = registry.run_tool(
            "web_search",
            {"query": "Test Query"},
            actor_user_id=123,
        )

    assert run.result.ok is True
    assert "web result" in run.result.message.lower()
    assert run.result.data["query"] == "Test Query"
    assert len(run.result.data["results"]) == 2


def test_web_search_short_query_rejected(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    run = registry.run_tool(
        "web_search",
        {"query": "a"},
        actor_user_id=123,
    )
    assert run.result.ok is False
