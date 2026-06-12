"""WP1 acceptance tests: tool crashes, output defects, and trace latency."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.academic.service import AcademicService
from core.llm.engine import EngineHealth
from core.nl.tool_contracts import StructuredToolResult, ToolCategory
from core.nl.tool_contracts import ToolDefinition, EmptyArgs
from core.nl.tools import ToolRegistry


# ---------------------------------------------------------------------------
# WP1.1 — get_availability and generate_study_plan no longer crash
# ---------------------------------------------------------------------------

def test_get_availability_no_args_returns_ok(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool("get_availability", {}, actor_user_id=None)
    assert run.result.ok is True


def test_get_availability_with_explicit_dates_returns_ok(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool(
        "get_availability",
        {"start_date": "2026-06-12", "end_date": "2026-06-18"},
        actor_user_id=None,
    )
    assert run.result.ok is True


def test_get_availability_invalid_date_returns_structured_error(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool(
        "get_availability",
        {"start_date": "not-a-date"},
        actor_user_id=None,
    )
    assert run.result.ok is False
    assert "Invalid date" in run.result.message


def test_generate_study_plan_no_args_returns_ok(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool("generate_study_plan", {}, actor_user_id=None)
    assert run.result.ok is True


def test_generate_study_plan_with_reference_date_returns_ok(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool(
        "generate_study_plan",
        {"reference_date": "2026-06-12"},
        actor_user_id=None,
    )
    assert run.result.ok is True


def test_generate_study_plan_invalid_date_returns_structured_error(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool(
        "generate_study_plan",
        {"reference_date": "2026-13-01"},
        actor_user_id=None,
    )
    assert run.result.ok is False
    assert "Invalid date" in run.result.message


# ---------------------------------------------------------------------------
# WP1.2 — handler exceptions do not propagate from run_tool
# ---------------------------------------------------------------------------

def test_run_tool_handler_exception_returns_failed_result(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)

    def boom(args, actor_user_id):
        raise RuntimeError("boom")

    from core.nl.tool_contracts import ToolCategory, ActionTier
    from core.schemas import ActionTier as AT
    registry._tools["_test_boom"] = ToolDefinition(
        name="_test_boom",
        description="Raises unconditionally",
        category=ToolCategory.READ,
        args_schema=EmptyArgs,
        result_schema=StructuredToolResult,
        handler=boom,
    )
    run = registry.run_tool("_test_boom", {}, actor_user_id=None)
    assert run.result.ok is False
    assert "Tool failed" in run.result.message


def test_run_tool_handler_exception_logs_event(tmp_db: Path, caplog) -> None:
    registry = ToolRegistry(tmp_db)

    def boom(args, actor_user_id):
        raise RuntimeError("intentional")

    registry._tools["_test_boom2"] = ToolDefinition(
        name="_test_boom2",
        description="Raises unconditionally",
        category=ToolCategory.READ,
        args_schema=EmptyArgs,
        result_schema=StructuredToolResult,
        handler=boom,
    )
    with caplog.at_level(logging.ERROR, logger="core.nl.tools"):
        registry.run_tool("_test_boom2", {}, actor_user_id=None)
    events = [r for r in caplog.records if getattr(r, "event_type", None) == "tool_handler_exception"]
    assert events, "Expected tool_handler_exception log record"


# ---------------------------------------------------------------------------
# WP1.3 — get_local_llm_status uses engine.health()
# ---------------------------------------------------------------------------

def test_get_local_llm_status_reachable(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, ollama_model="llama3.1:8b")
    mock_health = EngineHealth(
        available=True,
        model="llama3.1:8b",
        models=["llama3.1:8b", "llama2:7b"],
    )
    with patch.object(registry._engine().__class__, "health", return_value=mock_health):
        with patch.object(type(registry), "_engine") as mock_engine_factory:
            mock_engine = MagicMock()
            mock_engine.health.return_value = mock_health
            mock_engine.model = "llama3.1:8b"
            mock_engine_factory.return_value = mock_engine
            run = registry.run_tool("get_local_llm_status", {}, actor_user_id=None)
    assert run.result.ok is True
    assert run.result.data["status"] == "reachable"
    assert run.result.data["configured_model_present"] is True


def test_get_local_llm_status_unreachable(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    mock_health = EngineHealth(
        available=False,
        model="llama3.1:8b",
        error="Connection refused",
    )
    with patch.object(type(registry), "_engine") as mock_engine_factory:
        mock_engine = MagicMock()
        mock_engine.health.return_value = mock_health
        mock_engine_factory.return_value = mock_engine
        run = registry.run_tool("get_local_llm_status", {}, actor_user_id=None)
    assert run.result.ok is False
    assert "unreachable" in run.result.message.lower()


# ---------------------------------------------------------------------------
# WP1.4 — duration formatting uses divmod(minutes, 60), not // 2
# ---------------------------------------------------------------------------

def test_fmt_dur_120_minutes_renders_2h00(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    assert registry._fmt_dur(120) == "2h00"


def test_fmt_dur_90_minutes_renders_1h30(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    assert registry._fmt_dur(90) == "1h30"


def test_fmt_dur_0_minutes_renders_0h00(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    assert registry._fmt_dur(0) == "0h00"


def test_today_overview_message_uses_correct_duration(tmp_db: Path) -> None:
    """today overview 120 min → 2h00, not 60h00."""
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool("get_today_overview", {}, actor_user_id=None)
    assert run.result.ok is True
    # 60h never appears in a valid duration
    assert "60h" not in run.result.message


def test_availability_message_uses_correct_duration(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool("get_availability", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "60h" not in run.result.message


def test_study_plan_message_uses_correct_duration(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    service = AcademicService(tmp_db)
    service.add_assignment(title="Test", due_at="2026-06-30 23:59")
    run = registry.run_tool("generate_study_plan", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "60h" not in run.result.message


def test_deadline_risk_message_uses_correct_duration(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    run = registry.run_tool("explain_deadline_risk", {}, actor_user_id=None)
    assert run.result.ok is True
    assert "60h" not in run.result.message
