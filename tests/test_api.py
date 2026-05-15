"""FastAPI integration tests for Phase 1 routes."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Settings
from core.skill_registry import SkillRegistry


def test_health_endpoint(settings: Settings) -> None:
    """GET /health should return the healthcheck payload."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_endpoint(settings: Settings) -> None:
    """GET /status should return the status skill output."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert "Atenas" in response.json()["response"]


def test_skills_endpoint(settings: Settings) -> None:
    """GET /skills should list the registered status skill."""

    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/skills")

    assert response.status_code == 200
    assert "status" in response.json()["response"]

