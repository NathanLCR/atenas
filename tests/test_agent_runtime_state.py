"""Tests for durable NL agent runtime state."""

from __future__ import annotations

from pathlib import Path

from core.db import get_connection, init_db
from core.nl.runtime_state import AgentRuntimeStore
from core.nl.tool_contracts import PendingToolAction
from core.schemas import (
    ActionCriticality,
    ActionOrigin,
    ActionProposal,
    ActionTier,
)


def test_runtime_tables_exist(tmp_db: Path) -> None:
    init_db(tmp_db)
    with get_connection(tmp_db) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "agent_threads" in tables
    assert "pending_actions" in tables


def test_pending_action_round_trips(tmp_db: Path) -> None:
    store = AgentRuntimeStore(tmp_db)
    pending = PendingToolAction(
        tool_name="delete_modules",
        confirmation_message='Delete module? Reply "yes" to confirm or "no" to cancel.',
        proposal=ActionProposal(
            action_type="delete_modules",
            payload={"module_ids": ["m1"], "actor_user_id": 123},
            confidence=1.0,
            origin=ActionOrigin.TELEGRAM_NL,
            criticality=ActionCriticality.DESTRUCTIVE,
            action_tier=ActionTier.CONFIRM_FIRST,
        ),
    )

    record = store.save_pending_action(
        actor_user_id=123,
        channel="telegram",
        pending=pending,
    )

    loaded = store.get_active_pending_action(actor_user_id=123, channel="telegram")
    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.pending.tool_name == "delete_modules"
    assert loaded.pending.proposal.action_type == "delete_modules"
