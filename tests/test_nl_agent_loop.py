"""Tests for the tool-calling NL agent loop."""

from __future__ import annotations

import json
import logging
from pathlib import Path

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
