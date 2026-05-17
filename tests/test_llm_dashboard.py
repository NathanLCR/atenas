"""Tests for Phase 7 LLM dashboard route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from core.skill_registry import SkillRegistry


def test_llm_route_returns_200(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/llm")

    assert response.status_code == 200


def test_llm_route_empty_state(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/llm")

    assert response.status_code == 200
    assert "No LLM calls recorded" in response.text
