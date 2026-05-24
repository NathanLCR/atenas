"""Tests for AgentTraceStore — trace lifecycle and summary safety."""

from __future__ import annotations

from pathlib import Path

from core.db import init_db
from core.nl.traces import AgentTraceStore


def test_init_db_creates_trace_tables(tmp_path: Path) -> None:
    """init_db should create agent_traces and agent_trace_steps."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)
    assert store.list_recent() == []


def test_trace_lifecycle(tmp_path: Path) -> None:
    """Record start, step, and finish."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)

    trace_id = store.start_trace(
        actor_user_id=123,
        model="llama3.1:8b",
        user_message="mark my essay as done",
    )
    assert trace_id is not None

    store.record_step(
        trace_id,
        step_index=0,
        tool_name="set_assignment_status",
        arguments={"assignment": "ML essay", "status": "done"},
        ok=True,
        executed=True,
        pending=False,
        message="Assignment status updated to done.",
        latency_ms=150,
    )

    store.finish_trace(
        trace_id,
        status="success",
        final_message="Marked ML essay as done.",
        tool_call_count=1,
        latency_ms=1500,
    )

    rows = store.list_recent()
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "success"
    assert row["user_message_summary"] == "mark my essay as done"
    assert row["final_message_summary"] == "Marked ML essay as done."
    assert row["tool_call_count"] == 1


def test_trace_long_fields_are_summarized(tmp_path: Path) -> None:
    """Long and sensitive fields must be truncated, not stored raw."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)

    long_msg = "x" * 500
    trace_id = store.start_trace(
        actor_user_id=123,
        model="llama3.1:8b",
        user_message=long_msg,
    )

    store.record_step(
        trace_id,
        step_index=0,
        tool_name="update_memory",
        arguments={"content": long_msg, "summary": long_msg},
        ok=True,
        executed=True,
        pending=False,
        message=long_msg,
    )

    store.finish_trace(
        trace_id,
        status="success",
        final_message=long_msg,
        tool_call_count=1,
    )

    rows = store.list_recent()
    row = rows[0]
    assert len(row["user_message_summary"]) <= 243  # 240 + "..."
    assert row["user_message_summary"].endswith("...")
    assert row["final_message_summary"].endswith("...")


def test_list_recent_returns_newest_first(tmp_path: Path) -> None:
    """list_recent should order by started_at DESC."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)

    import time as _time
    id_a = store.start_trace(actor_user_id=1, user_message="first")
    _time.sleep(0.01)
    id_b = store.start_trace(actor_user_id=2, user_message="second")
    store.finish_trace(id_a, status="success")
    store.finish_trace(id_b, status="success")

    rows = store.list_recent(limit=10)
    assert rows[0]["actor_user_id"] == 2
    assert rows[1]["actor_user_id"] == 1


def test_list_recent_limit(tmp_path: Path) -> None:
    """list_recent should respect the limit parameter."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)

    for i in range(5):
        tid = store.start_trace(actor_user_id=i, user_message=f"msg {i}")
        store.finish_trace(tid, status="success")

    assert len(store.list_recent(limit=2)) == 2


def test_list_recent_empty(tmp_path: Path) -> None:
    """Empty DB should return empty list."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)
    assert store.list_recent() == []


def test_record_step_long_args_summarized(tmp_path: Path) -> None:
    """Step arguments_summary should not contain full text bodies."""
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    store = AgentTraceStore(db_path)

    trace_id = store.start_trace(actor_user_id=1, user_message="test")
    long_args = {"body": "x" * 5000, "title": "y" * 100}
    store.record_step(
        trace_id,
        step_index=0,
        tool_name="write_memory",
        arguments=long_args,
        ok=True,
        executed=True,
        pending=False,
    )

    rows = store.list_recent()
    # We need to also check step data - we can access via raw query
    from core.db import get_connection
    with get_connection(db_path) as conn:
        step = conn.execute(
            "SELECT arguments_summary FROM agent_trace_steps WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert step is not None
    summary = step["arguments_summary"]
    # Should be the summarized str representation, not the raw 5000-char body
    assert len(summary) < 500
