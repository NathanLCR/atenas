"""FastAPI integration tests for Phase 1 routes."""

import subprocess
import sys

from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Settings
from core.skill_registry import SkillRegistry


def test_importing_app_main_does_not_build_app() -> None:
    """`import app.main` must be side-effect free; app builds lazily (PEP 562)."""

    code = (
        "import app.main as m;"
        "assert m._app is None, 'app built on import';"
        "assert type(m.app).__name__ == 'FastAPI';"
        "assert m._app is not None, 'app not cached after access';"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


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


def test_placeholder_telegram_token_does_not_block_startup(settings: Settings) -> None:
    """A scaffolded Telegram token placeholder should be treated as disabled."""

    settings_data = settings.model_dump()
    settings_data["telegram_bot_token"] = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    runtime_settings = Settings(_env_file=None, **settings_data)
    app = create_app(settings=runtime_settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
