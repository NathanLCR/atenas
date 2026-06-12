"""WP2 acceptance tests: policy/audit governance on every action."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from core.action_executor import ActionExecutor
from core.db import get_connection
from core.nl.runtime_state import AgentRuntimeStore
from core.nl.tool_contracts import PendingToolAction, StructuredToolResult
from core.nl.tools import ToolRegistry
from core.policy_engine import PolicyDecision, PolicyEngine
from core.schemas import (
    ActionCriticality,
    ActionOrigin,
    ActionOutcome,
    ActionProposal,
    ActionTier,
)
from core.skill_registry import SkillInfo, SkillRegistry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_pending_action(action_type: str = "archive_note", actor_user_id: int = 123) -> PendingToolAction:
    return PendingToolAction(
        tool_name=action_type,
        confirmation_message=f'Confirm {action_type}? Reply "yes" or "no".',
        proposal=ActionProposal(
            action_type=action_type,
            payload={"actor_user_id": actor_user_id, "note_id": 1},
            confidence=1.0,
            origin=ActionOrigin.TELEGRAM_NL,
            criticality=ActionCriticality.LOCAL_WRITE,
            action_tier=ActionTier.CONFIRM_FIRST,
        ),
    )


class _DenyAllPolicyEngine(PolicyEngine):
    """Policy engine that rejects every action regardless of type."""

    def check(self, proposal: ActionProposal) -> PolicyDecision:
        return PolicyDecision(
            allowed=False,
            outcome=ActionOutcome.BLOCKED,
            reason=f"Denied by test policy: {proposal.action_type}",
        )


def _make_update(user_id: int = 123, text: str = "") -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_bot_context(tmp_db: Path) -> SimpleNamespace:
    settings = Settings(
        _env_file=None,
        telegram_allowed_user_ids=[123],
        data_dir=tmp_db.parent,
    )
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
        bot_data={"settings": settings},
        chat_data={},
    )


def _make_app(settings: Settings):
    from app.main import create_app
    return create_app(settings=settings, registry=SkillRegistry())


# ---------------------------------------------------------------------------
# WP2.1 — add_* tools route through PolicyEngine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name,args", [
    ("add_assignment", {"title": "Essay", "due_at": "2026-06-30 23:59"}),
    ("add_note", {"title": "My note", "body": "some content"}),
    ("add_class_session", {"title": "DL", "weekday": 0, "start_time": "10:00", "end_time": "12:00"}),
    ("add_work_shift", {"title": "Work", "start_at": "2026-06-20 14:00", "end_at": "2026-06-20 22:00"}),
])
def test_add_tools_consult_and_respect_policy_deny(
    tmp_db: Path, tool_name: str, args: dict
) -> None:
    """A deny-all policy engine must block all four add_* auto-tier tools."""
    deny_executor = ActionExecutor(policy_engine=_DenyAllPolicyEngine())
    registry = ToolRegistry(tmp_db, action_executor=deny_executor)
    run = registry.run_tool(tool_name, args, actor_user_id=42)
    assert run.result.ok is False
    assert "Denied by test policy" in run.result.message


def test_add_assignment_emits_action_executed_log_on_success(tmp_db: Path, caplog) -> None:
    """Successful add_assignment must emit action_executed with the right action_type."""
    registry = ToolRegistry(tmp_db)
    with caplog.at_level(logging.INFO, logger="core.action_executor"):
        registry.run_tool(
            "add_assignment",
            {"title": "Essay", "due_at": "2026-06-30 23:59"},
            actor_user_id=42,
        )
    events = [r for r in caplog.records if getattr(r, "event_type", None) == "action_executed"]
    assert events, "Expected action_executed log record"
    assert events[0].action_type == "add_assignment"
    assert events[0].actor_user_id == 42


def test_add_note_emits_action_executed_log_on_success(tmp_db: Path, caplog) -> None:
    registry = ToolRegistry(tmp_db)
    with caplog.at_level(logging.INFO, logger="core.action_executor"):
        registry.run_tool(
            "add_note",
            {"title": "My note", "body": "hello world"},
            actor_user_id=42,
        )
    events = [r for r in caplog.records if getattr(r, "event_type", None) == "action_executed"]
    assert events, "Expected action_executed log record"
    assert events[0].action_type == "add_note"


def test_add_class_session_emits_action_executed_log_on_success(tmp_db: Path, caplog) -> None:
    registry = ToolRegistry(tmp_db)
    with caplog.at_level(logging.INFO, logger="core.action_executor"):
        registry.run_tool(
            "add_class_session",
            {"title": "DL lecture", "weekday": 0, "start_time": "10:00", "end_time": "12:00"},
            actor_user_id=42,
        )
    events = [r for r in caplog.records if getattr(r, "event_type", None) == "action_executed"]
    assert events
    assert events[0].action_type == "add_class_session"


def test_add_work_shift_emits_action_executed_log_on_success(tmp_db: Path, caplog) -> None:
    registry = ToolRegistry(tmp_db)
    with caplog.at_level(logging.INFO, logger="core.action_executor"):
        registry.run_tool(
            "add_work_shift",
            {"title": "Work", "start_at": "2026-06-20 14:00", "end_at": "2026-06-20 22:00"},
            actor_user_id=42,
        )
    events = [r for r in caplog.records if getattr(r, "event_type", None) == "action_executed"]
    assert events
    assert events[0].action_type == "add_work_shift"


# ---------------------------------------------------------------------------
# WP2.2 — pending action status is accurate (executed / failed / cancelled)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pending_action_marked_executed_on_success(tmp_db: Path) -> None:
    """Successful execute_pending must mark the durable record 'executed'."""
    from app.bot import _execute_pending_action

    store = AgentRuntimeStore(tmp_db)
    pending = _make_pending_action("archive_note", actor_user_id=123)
    record = store.save_pending_action(actor_user_id=123, channel="telegram", pending=pending)

    fake_registry = MagicMock()
    fake_registry.execute_pending.return_value = StructuredToolResult(
        ok=True, message="Archived.", executed=True
    )

    with patch("app.bot._build_nl_tool_registry", return_value=fake_registry):
        await _execute_pending_action(
            _make_update(123),
            _make_bot_context(tmp_db),
            user_id=123,
            pending=pending,
            pending_record=record,
            runtime_store=store,
        )

    with get_connection(tmp_db) as conn:
        row = conn.execute("SELECT status FROM pending_actions WHERE id = ?", (record.id,)).fetchone()
    assert row["status"] == "executed"


@pytest.mark.asyncio
async def test_pending_action_marked_failed_on_policy_block(tmp_db: Path) -> None:
    """Policy-blocked execute_pending must mark the durable record 'failed'."""
    from app.bot import _execute_pending_action

    store = AgentRuntimeStore(tmp_db)
    pending = _make_pending_action("archive_note", actor_user_id=123)
    record = store.save_pending_action(actor_user_id=123, channel="telegram", pending=pending)

    fake_registry = MagicMock()
    fake_registry.execute_pending.return_value = StructuredToolResult(
        ok=False, message="Blocked by policy: forbidden action.", executed=False
    )

    update = _make_update(123)
    with patch("app.bot._build_nl_tool_registry", return_value=fake_registry):
        await _execute_pending_action(
            update,
            _make_bot_context(tmp_db),
            user_id=123,
            pending=pending,
            pending_record=record,
            runtime_store=store,
        )

    with get_connection(tmp_db) as conn:
        row = conn.execute("SELECT status FROM pending_actions WHERE id = ?", (record.id,)).fetchone()
    assert row["status"] == "failed"
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "policy" in reply.lower() or "Blocked" in reply


@pytest.mark.asyncio
async def test_pending_action_marked_cancelled_on_actor_mismatch(tmp_db: Path) -> None:
    """Actor-mismatch execute_pending must mark the durable record 'cancelled'."""
    from app.bot import _execute_pending_action

    store = AgentRuntimeStore(tmp_db)
    pending = _make_pending_action("archive_note", actor_user_id=123)
    record = store.save_pending_action(actor_user_id=123, channel="telegram", pending=pending)

    fake_registry = MagicMock()
    fake_registry.execute_pending.return_value = StructuredToolResult(
        ok=False,
        message="Confirmation cancelled because the Telegram user changed.",
        executed=False,
    )

    with patch("app.bot._build_nl_tool_registry", return_value=fake_registry):
        await _execute_pending_action(
            _make_update(123),
            _make_bot_context(tmp_db),
            user_id=123,
            pending=pending,
            pending_record=record,
            runtime_store=store,
        )

    with get_connection(tmp_db) as conn:
        row = conn.execute("SELECT status FROM pending_actions WHERE id = ?", (record.id,)).fetchone()
    assert row["status"] == "cancelled"


# ---------------------------------------------------------------------------
# WP2.3 — /confirm command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_command_executes_pending_action(tmp_db: Path) -> None:
    """/confirm must execute the active durable pending action."""
    from app.bot import confirm_command

    store = AgentRuntimeStore(tmp_db)
    pending = _make_pending_action("archive_note", actor_user_id=123)
    store.save_pending_action(actor_user_id=123, channel="telegram", pending=pending)

    fake_registry = MagicMock()
    fake_registry.execute_pending.return_value = StructuredToolResult(
        ok=True, message="Note archived.", executed=True
    )

    update = _make_update(123, "/confirm")
    with patch("app.bot._build_nl_tool_registry", return_value=fake_registry):
        await confirm_command(update, _make_bot_context(tmp_db))

    update.effective_message.reply_text.assert_awaited_once()
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "archived" in reply.lower()


@pytest.mark.asyncio
async def test_confirm_command_no_pending_replies_safely(tmp_db: Path) -> None:
    """/confirm with no pending action must reply 'No pending action.'."""
    from app.bot import confirm_command

    update = _make_update(123, "/confirm")
    await confirm_command(update, _make_bot_context(tmp_db))

    update.effective_message.reply_text.assert_awaited_once_with("No pending action.")


# ---------------------------------------------------------------------------
# WP2.4 — Command audit logging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_registry_dispatch_emits_command_executed(caplog) -> None:
    """SkillRegistry.dispatch must emit command_executed with actor and command."""

    async def handler(command: str, args: str, user_id: int) -> str:
        return "ok"

    reg = SkillRegistry()
    reg.register(SkillInfo(
        name="status",
        description="Status",
        commands=("/status",),
        enabled=True,
        handler=handler,
    ))

    with caplog.at_level(logging.INFO, logger="core.skill_registry"):
        await reg.dispatch("/status", user_id=42)

    events = [r for r in caplog.records if getattr(r, "event_type", None) == "command_executed"]
    assert events, "Expected command_executed log from SkillRegistry.dispatch"
    assert events[0].actor_user_id == 42
    assert events[0].command == "/status"


@pytest.mark.asyncio
async def test_audit_cmd_decorator_emits_command_executed(caplog) -> None:
    """_audit_cmd must emit command_executed with actor_user_id and command name."""
    from app.bot import _audit_cmd

    async def noop(update, context) -> None:
        pass

    decorated = _audit_cmd(noop)
    update = _make_update(99, "/ping")

    with caplog.at_level(logging.INFO, logger="app.bot"):
        await decorated(update, SimpleNamespace(bot=SimpleNamespace()))

    events = [r for r in caplog.records if getattr(r, "event_type", None) == "command_executed"]
    assert events, "Expected command_executed from _audit_cmd"
    assert events[0].actor_user_id == 99
    assert events[0].command == "/ping"


def test_add_note_action_executed_does_not_log_note_body(tmp_db: Path, caplog) -> None:
    """Note body must not appear verbatim in action_executed payload_summary."""
    registry = ToolRegistry(tmp_db)
    secret_body = "TOP SECRET NOTE BODY do not log this verbatim"
    with caplog.at_level(logging.INFO, logger="core.action_executor"):
        registry.run_tool(
            "add_note",
            {"title": "secret", "body": secret_body},
            actor_user_id=42,
        )
    events = [r for r in caplog.records if getattr(r, "event_type", None) == "action_executed"]
    assert events, "Expected action_executed record"
    summary_str = str(getattr(events[0], "payload_summary", ""))
    assert secret_body not in summary_str


# ---------------------------------------------------------------------------
# WP2.5 — X-Forwarded-For guard
# ---------------------------------------------------------------------------

def test_loopback_peer_no_xff_is_allowed(settings: Settings) -> None:
    """Loopback peer (testclient) with no X-Forwarded-For must reach the API."""
    from fastapi.testclient import TestClient

    with TestClient(_make_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_loopback_peer_with_non_loopback_xff_is_denied(settings: Settings) -> None:
    """Loopback peer with a non-loopback X-Forwarded-For must be denied."""
    from fastapi.testclient import TestClient

    with TestClient(_make_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/health", headers={"X-Forwarded-For": "203.0.113.1"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_loopback_peer_with_spoofed_xff_loopback_is_denied(settings: Settings) -> None:
    """Non-loopback socket peer spoofing X-Forwarded-For: 127.0.0.1 must be denied."""
    import httpx

    transport = httpx.ASGITransport(app=_make_app(settings), client=("203.0.113.1", 9999))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health", headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403
