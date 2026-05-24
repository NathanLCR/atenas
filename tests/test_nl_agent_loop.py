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
from core.nl.tool_contracts import ToolCategory
from core.nl.toolsets import ToolsetName
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


DESTRUCTIVE_TOOLSETS = {
    ToolsetName.TELEGRAM_SAFE,
    ToolsetName.TELEGRAM_DESTRUCTIVE,
}


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
    agent = AgentLoop(registry=registry, client=client, toolsets=DESTRUCTIVE_TOOLSETS)

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


def test_auto_tier_assignment_hours_executes_without_confirmation(
    tmp_db: Path,
    caplog,
) -> None:
    service = AcademicService(tmp_db)
    added = service.add_assignment(title="ML essay", due_at="2026-06-01 23:59", estimated_hours=5.0)
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "set_assignment_hours",
            "arguments": {"assignment": "ML essay", "completed_hours": 2.0},
        },
        {"type": "final", "message": "Progress updated\n\n#........ ‑ ML essay\nCompleted: 2.00h\nRemaining: 3.00h"},
    ])
    agent = AgentLoop(registry=registry, client=client)
    caplog.set_level(logging.INFO, logger="core.action_executor")

    result = agent.run("I have worked 2 hours on my ML essay", actor_user_id=123)

    assert result.pending_action is None
    assert result.message == "Progress updated\n\n#........ ‑ ML essay\nCompleted: 2.00h\nRemaining: 3.00h"
    assignment = service.repository.get_assignment_by_id(added.record_id or "")
    assert assignment is not None
    assert assignment.completed_hours == 2.0
    audit = [record for record in caplog.records if record.message == "action_executed"][-1]
    assert audit.action_type == "set_assignment_hours"
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
    agent = AgentLoop(registry=registry, client=client, toolsets=DESTRUCTIVE_TOOLSETS)

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
    agent = AgentLoop(registry=registry, client=client, toolsets=DESTRUCTIVE_TOOLSETS)

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


def test_web_search_returns_pending_confirm(tmp_db: Path) -> None:
    """Web search should return a pending confirmation via the gate action."""
    registry = ToolRegistry(tmp_db, web_enabled=True)
    mock_response = json.dumps([
        "Test Query",
        ["Result 1", "Result 2"],
        ["Snippet 1", "Snippet 2"],
        ["http://example.com/1", "http://example.com/2"],
    ]).encode("utf-8")

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda s, *a: None
        mock_urlopen.return_value.read = lambda: mock_response

        run = registry.run_tool(
            "web_search",
            {"query": "Test Query"},
            actor_user_id=123,
        )

    assert run.result.ok is True
    assert run.result.pending is True
    assert run.pending_action is not None
    assert run.pending_action.tool_name == "web_search"


def test_web_search_short_query_rejected(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    run = registry.run_tool(
        "web_search",
        {"query": "a"},
        actor_user_id=123,
    )
    assert run.result.ok is False


def test_agent_loop_uses_telegram_safe_toolset_by_default(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    client = FakeToolClient([
        {"type": "final", "message": "done"},
    ])
    agent = AgentLoop(registry=registry, client=client)

    agent.run("hello", actor_user_id=123)

    prompt = client.prompts[0]
    assert '"name": "set_assignment_status"' in prompt
    assert '"name": "web_search"' not in prompt
    assert '"name": "delete_modules"' not in prompt


def test_agent_loop_can_explicitly_expose_egress_and_destructive_toolsets(
    tmp_db: Path,
) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    client = FakeToolClient([
        {"type": "final", "message": "done"},
    ])
    agent = AgentLoop(
        registry=registry,
        client=client,
        toolsets={
            ToolsetName.TELEGRAM_SAFE,
            ToolsetName.TELEGRAM_EGRESS,
            ToolsetName.TELEGRAM_DESTRUCTIVE,
        },
    )

    agent.run("hello", actor_user_id=123)

    prompt = client.prompts[0]
    assert '"name": "web_search"' in prompt
    assert '"name": "delete_modules"' in prompt


def test_agent_loop_rejects_tool_hidden_by_selected_toolsets(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "web_search",
            "arguments": {"query": "python"},
        },
    ])
    agent = AgentLoop(registry=registry, client=client)

    result = agent.run("search the web for python", actor_user_id=123)

    assert result.pending_action is None
    assert result.message == "Tool not available in this agent context: web_search"


EXPECTED_TOOL_NAMES = {
    "list_modules",
    "list_assignments",
    "suggest_next_task",
    "search_notes",
    "retrieve_sources",
    "detect_duplicate_modules",
    "set_assignment_status",
    "set_assignment_hours",
    "delete_modules",
    "deduplicate_modules",
    "archive_note",
    "read_memory",
    "write_memory",
    "update_memory",
    "get_status",
    "get_today_overview",
    "get_week_overview",
    "get_deadlines",
    "get_availability",
    "list_class_sessions",
    "list_work_shifts",
    "get_local_llm_status",
    "generate_study_plan",
    "explain_deadline_risk",
    "add_assignment",
    "add_note",
    "add_class_session",
    "add_work_shift",
}


def test_catalog_tool_names_without_web(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=False)
    names = {t.name for t in registry.list_tools()}
    assert names == EXPECTED_TOOL_NAMES


def test_catalog_tool_names_with_web(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    names = {t.name for t in registry.list_tools()}
    assert names == EXPECTED_TOOL_NAMES | {"web_search"}


def test_all_act_tools_declare_explicit_tier(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    for tool in registry.list_tools():
        if tool.category == ToolCategory.ACT or tool.category == ToolCategory.WEB:
            assert tool.action_tier is not None, f"{tool.name} missing action_tier"


def test_schemas_for_llm_structure(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    schemas = registry.schemas_for_llm()
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "category" in schema
        assert "parameters" in schema
        assert "returns" in schema


# ── Agent Trace Integration Tests ──────────────────────────────────────────


def test_auto_tier_creates_success_trace(tmp_db: Path) -> None:
    """An auto-tier write should create a trace with tool call and success."""
    from core.nl.traces import AgentTraceStore

    trace_store = AgentTraceStore(tmp_db)
    service = AcademicService(tmp_db)
    service.add_assignment(title="ML essay", due_at="2026-06-01 23:59")
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "set_assignment_status",
            "arguments": {"assignment": "ML essay", "status": "done"},
        },
        {"type": "final", "message": "Marked ML essay as done."},
    ])
    agent = AgentLoop(registry=registry, client=client, trace_store=trace_store)

    result = agent.run("mark my ML essay done", actor_user_id=123)

    assert result.pending_action is None
    traces = trace_store.list_recent(limit=5)
    assert len(traces) >= 1
    latest = traces[0]
    assert latest["status"] == "success"
    assert latest["user_message_summary"] == "mark my ML essay done"


def test_confirm_first_action_creates_pending_trace(tmp_db: Path) -> None:
    """A confirm-first action should create a trace with pending action type."""
    from core.nl.traces import AgentTraceStore

    service = AcademicService(tmp_db)
    mod = service.create_module(name="ToDelete", code="DEL")
    trace_store = AgentTraceStore(tmp_db)
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "delete_modules",
            "arguments": {"module_ids": [mod.id]},
        },
    ])
    agent = AgentLoop(
        registry=registry,
        client=client,
        trace_store=trace_store,
        toolsets=DESTRUCTIVE_TOOLSETS,
    )

    result = agent.run("delete module", actor_user_id=123)

    assert result.pending_action is not None
    traces = trace_store.list_recent(limit=5)
    latest = traces[0]
    assert latest["status"] == "success"
    assert latest["pending_action_type"] == "delete_modules"
    assert latest["tool_call_count"] >= 1


def test_invalid_decision_creates_error_trace(tmp_db: Path) -> None:
    """Invalid model JSON should create an error trace."""
    from core.nl.traces import AgentTraceStore

    class InvalidClient:
        def generate(self, prompt: str):
            return OllamaResponse(text="not valid json at all", model="test")

    trace_store = AgentTraceStore(tmp_db)
    registry = ToolRegistry(tmp_db)
    agent = AgentLoop(registry=registry, client=InvalidClient(), trace_store=trace_store)

    agent.run("hello", actor_user_id=123)

    traces = trace_store.list_recent(limit=5)
    latest = traces[0]
    assert latest["status"] == "error"


def test_llm_unavailable_creates_llm_error_trace(tmp_db: Path) -> None:
    """LLM unavailable should create an llm_error trace."""
    from core.nl.traces import AgentTraceStore

    class UnavailableClient:
        def generate(self, prompt: str):
            raise ConnectionError("Ollama not running")

    trace_store = AgentTraceStore(tmp_db)
    registry = ToolRegistry(tmp_db)
    agent = AgentLoop(registry=registry, client=UnavailableClient(), trace_store=trace_store)

    agent.run("hello", actor_user_id=123)

    traces = trace_store.list_recent(limit=5)
    latest = traces[0]
    assert latest["status"] == "llm_error"
