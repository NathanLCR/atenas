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
