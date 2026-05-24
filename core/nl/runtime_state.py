"""SQLite-backed runtime state for the NL agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.db import get_connection, init_db
from core.nl.tool_contracts import PendingToolAction
from core.schemas import ActionProposal, StrictModel, new_id
from core.utils import utc_now


class AgentThreadRecord(StrictModel):
    """Persisted conversation state for one actor/channel pair."""

    id: str
    actor_user_id: int
    channel: str
    status: str
    conversation: list[dict[str, str]]
    selected_tools: list[str]
    created_at: str
    updated_at: str


class PendingActionRecord(StrictModel):
    """Persisted confirm-first action awaiting Telegram confirmation."""

    id: str
    thread_id: str
    actor_user_id: int
    channel: str
    pending: PendingToolAction
    status: str
    created_at: str
    updated_at: str
    expires_at: str | None = None


class AgentRuntimeStore:
    """Store durable NL agent thread state and pending actions."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def get_or_create_thread(
        self,
        *,
        actor_user_id: int,
        channel: str = "telegram",
    ) -> AgentThreadRecord:
        """Return the active thread for an actor/channel, creating one."""

        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM agent_threads
                WHERE actor_user_id = ? AND channel = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (actor_user_id, channel),
            ).fetchone()
            if row is not None:
                return _thread_from_row(row)

            now = utc_now()
            thread_id = new_id()
            conn.execute(
                """
                INSERT INTO agent_threads (
                    id, actor_user_id, channel, status, conversation_json,
                    selected_tools_json, created_at, updated_at
                )
                VALUES (?, ?, ?, 'active', '[]', '[]', ?, ?)
                """,
                (thread_id, actor_user_id, channel, now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM agent_threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
        return _thread_from_row(row)

    def save_conversation(
        self,
        *,
        actor_user_id: int,
        channel: str,
        conversation: list[dict[str, str]],
    ) -> AgentThreadRecord:
        """Persist the latest sanitized conversation for an actor/channel."""

        thread = self.get_or_create_thread(
            actor_user_id=actor_user_id,
            channel=channel,
        )
        now = utc_now()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE agent_threads
                SET conversation_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(conversation), now, thread.id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM agent_threads WHERE id = ?",
                (thread.id,),
            ).fetchone()
        return _thread_from_row(row)

    def save_pending_action(
        self,
        *,
        actor_user_id: int,
        channel: str,
        pending: PendingToolAction,
    ) -> PendingActionRecord:
        """Persist a confirm-first action before the user sees the prompt."""

        thread = self.get_or_create_thread(
            actor_user_id=actor_user_id,
            channel=channel,
        )
        pending_id = new_id()
        now = utc_now()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pending_actions (
                    id, thread_id, actor_user_id, tool_name, action_type,
                    proposal_json, confirmation_message, status, created_at,
                    updated_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, NULL)
                """,
                (
                    pending_id,
                    thread.id,
                    actor_user_id,
                    pending.tool_name,
                    pending.proposal.action_type,
                    pending.proposal.model_dump_json(),
                    pending.confirmation_message,
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT pending_actions.*, agent_threads.channel
                FROM pending_actions
                JOIN agent_threads ON agent_threads.id = pending_actions.thread_id
                WHERE pending_actions.id = ?
                """,
                (pending_id,),
            ).fetchone()
        return _pending_from_row(row)

    def get_active_pending_action(
        self,
        *,
        actor_user_id: int,
        channel: str = "telegram",
    ) -> PendingActionRecord | None:
        """Return the newest pending action for this actor/channel."""

        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT pending_actions.*, agent_threads.channel
                FROM pending_actions
                JOIN agent_threads ON agent_threads.id = pending_actions.thread_id
                WHERE pending_actions.actor_user_id = ?
                  AND pending_actions.status = 'pending'
                  AND agent_threads.channel = ?
                  AND agent_threads.status = 'active'
                ORDER BY pending_actions.created_at DESC
                LIMIT 1
                """,
                (actor_user_id, channel),
            ).fetchone()
        if row is None:
            return None
        return _pending_from_row(row)

    def mark_pending_action(
        self,
        pending_id: str,
        *,
        status: str,
    ) -> None:
        """Mark a pending action as executed, cancelled, expired, or similar."""

        now = utc_now()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE pending_actions
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now, pending_id),
            )
            conn.commit()


def _thread_from_row(row: Any) -> AgentThreadRecord:
    return AgentThreadRecord(
        id=row["id"],
        actor_user_id=row["actor_user_id"],
        channel=row["channel"],
        status=row["status"],
        conversation=json.loads(row["conversation_json"]),
        selected_tools=json.loads(row["selected_tools_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _pending_from_row(row: Any) -> PendingActionRecord:
    proposal = ActionProposal.model_validate_json(row["proposal_json"])
    pending = PendingToolAction(
        tool_name=row["tool_name"],
        proposal=proposal,
        confirmation_message=row["confirmation_message"],
    )
    return PendingActionRecord(
        id=row["id"],
        thread_id=row["thread_id"],
        actor_user_id=row["actor_user_id"],
        channel=row["channel"],
        pending=pending,
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
    )
