"""Tests for the Phase 2 read-only dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from core.db import get_connection
from core.skill_registry import SkillRegistry


def test_home_route_returns_200(settings: Settings) -> None:
    """Dashboard home should render with the app name."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/")

    assert response.status_code == 200
    assert settings.app_name in response.text


def test_logs_route_returns_200(settings: Settings) -> None:
    """Dashboard logs should render even when no records exist."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/logs")

    assert response.status_code == 200


def test_logs_route_empty_state(settings: Settings) -> None:
    """An empty llm_calls table should show the empty state."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_calls (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    estimated_cost REAL,
                    success INTEGER NOT NULL,
                    latency_ms INTEGER,
                    schema_valid INTEGER,
                    policy_passed INTEGER,
                    outcome TEXT NOT NULL DEFAULT 'success',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/logs")

    assert response.status_code == 200
    assert "No LLM calls recorded yet." in response.text


def test_traces_route_returns_200(settings: Settings) -> None:
    """Dashboard traces should render even when no traces exist."""
    from app.main import create_app
    from core.skill_registry import SkillRegistry

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/traces")

    assert response.status_code == 200


def test_traces_route_empty_state(settings: Settings) -> None:
    """Empty agent_traces table should show the empty state."""
    from app.main import create_app
    from core.db import get_connection
    from core.skill_registry import SkillRegistry

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id TEXT PRIMARY KEY,
                    actor_user_id INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    model TEXT,
                    status TEXT NOT NULL,
                    user_message_summary TEXT NOT NULL,
                    final_message_summary TEXT,
                    tool_call_count INTEGER NOT NULL DEFAULT 0,
                    pending_action_type TEXT,
                    latency_ms INTEGER,
                    error TEXT
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/traces")

    assert response.status_code == 200
    assert "No agent traces recorded yet." in response.text


def test_traces_route_shows_stored_traces(settings: Settings) -> None:
    """Dashboard traces should display stored trace records."""
    from app.main import create_app
    from core.db import get_connection
    from core.skill_registry import SkillRegistry
    from core.schemas import new_id

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        connection = get_connection(settings.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id TEXT PRIMARY KEY,
                    actor_user_id INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    model TEXT,
                    status TEXT NOT NULL,
                    user_message_summary TEXT NOT NULL,
                    final_message_summary TEXT,
                    tool_call_count INTEGER NOT NULL DEFAULT 0,
                    pending_action_type TEXT,
                    latency_ms INTEGER,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO agent_traces
                    (id, actor_user_id, started_at, model, status,
                     user_message_summary, final_message_summary, tool_call_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (new_id(), 123, "2026-05-24T10:00:00", "llama3.1:8b",
                 "success", "mark my essay done", "Done!", 1),
            )
            connection.commit()
        finally:
            connection.close()

        response = client.get("/dashboard/traces")

    assert response.status_code == 200
    assert "mark my essay done" in response.text
    assert "success" in response.text
