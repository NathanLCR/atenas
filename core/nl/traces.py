"""Metadata-only agent trace persistence."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from core.db import connect
from core.schemas import new_id

logger = logging.getLogger(__name__)

_SUMMARY_MAX = 240


def _summarize(text: str, max_len: int = _SUMMARY_MAX) -> str:
    """Redact/summarize text to max_len characters."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


class AgentTraceStore:
    """Persist agent trace operational metadata to SQLite."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path

    def start_trace(
        self,
        *,
        actor_user_id: int | None = None,
        model: str | None = None,
        user_message: str,
    ) -> str:
        """Insert a new trace row and return its id."""
        trace_id = new_id()
        started_at = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO agent_traces
                    (id, actor_user_id, started_at, model, status, user_message_summary)
                VALUES (?, ?, ?, ?, 'in_progress', ?)
                """,
                (trace_id, actor_user_id, started_at, model, _summarize(user_message)),
            )
            conn.commit()
        return trace_id

    def record_step(
        self,
        trace_id: str,
        *,
        step_index: int,
        tool_name: str,
        arguments: dict[str, Any],
        ok: bool,
        executed: bool,
        pending: bool,
        message: str | None = None,
        latency_ms: int | None = None,
    ) -> str:
        """Record a single tool-call step."""
        step_id = new_id()
        created_at = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO agent_trace_steps
                    (id, trace_id, step_index, tool_name, arguments_summary,
                     ok, executed, pending, message_summary, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id, trace_id, step_index, tool_name,
                    _summarize(str(arguments)),
                    int(ok), int(executed), int(pending),
                    _summarize(message) if message else None,
                    latency_ms, created_at,
                ),
            )
            conn.commit()
        return step_id

    def finish_trace(
        self,
        trace_id: str,
        *,
        status: str,
        final_message: str | None = None,
        tool_call_count: int = 0,
        pending_action_type: str | None = None,
        latency_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        """Mark a trace as completed with final status."""
        completed_at = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE agent_traces
                SET completed_at = ?,
                    status = ?,
                    final_message_summary = ?,
                    tool_call_count = ?,
                    pending_action_type = ?,
                    latency_ms = ?,
                    error = ?
                WHERE id = ?
                """,
                (
                    completed_at, status,
                    _summarize(final_message) if final_message else None,
                    tool_call_count, pending_action_type, latency_ms,
                    error, trace_id,
                ),
            )
            conn.commit()

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent traces ordered by started_at DESC."""
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, actor_user_id, started_at, completed_at, model,
                       status, user_message_summary, final_message_summary,
                       tool_call_count, pending_action_type, latency_ms, error
                FROM agent_traces
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
