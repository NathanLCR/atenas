"""Tests for the deterministic status skill."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfoNotFoundError

import pytest

from core.skill_registry import SkillInfo, SkillRegistry
from skills.status.handler import _local_llm_status, handle_ping, handle_skills, handle_status


async def dummy_handler(command: str, args: str, user_id: int) -> str:
    """Return a no-op response for skill listing tests."""

    return "ok"


def test_handle_ping_returns_pong() -> None:
    """The ping handler should return the spec response."""

    assert handle_ping() == "🏓 pong"


def test_handle_status_with_empty_db_shows_zeros(tmp_db: Path) -> None:
    """Empty databases should produce a status summary with zero counts."""

    response = handle_status(tmp_db)

    assert "Atenas" in response
    assert "Active assignments: 0" in response
    assert "Deadlines this week: 0" in response
    assert "Work shifts this week: 0" in response


def test_handle_status_accepts_configured_timezone(tmp_db: Path) -> None:
    """The status window honors the configured IANA timezone (NFR-07)."""

    response = handle_status(tmp_db, "America/Sao_Paulo")

    assert "Active assignments: 0" in response
    assert "Deadlines this week: 0" in response


def test_handle_status_rejects_invalid_timezone(tmp_db: Path) -> None:
    """A bogus timezone surfaces, proving the zone is actually consumed."""

    with pytest.raises(ZoneInfoNotFoundError):
        handle_status(tmp_db, "Europe/Lndon")


def test_handle_status_marks_degraded_when_ollama_offline(tmp_db: Path) -> None:
    """The headline should not claim full health when local LLM is offline."""

    with patch(
        "urllib.request.urlopen",
        side_effect=OSError("connection refused"),
    ):
        response = handle_status(tmp_db, ollama_model="batiai/gemma4-e4b:q4")

    assert "Atenas — Degraded" in response
    assert "Ollama offline — model: batiai/gemma4-e4b:q4" in response


def test_local_llm_status_requires_configured_model_to_exist() -> None:
    """Ollama being reachable is not enough if the configured model is absent."""

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(
        {"models": [{"name": "llama3.1:8b"}]}
    ).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        status = _local_llm_status("http://localhost:11434", "batiai/gemma4-e4b:q4")

    assert status.available is False
    assert "model missing: batiai/gemma4-e4b:q4" in status.message


def test_local_llm_status_available_when_configured_model_exists() -> None:
    """The LLM status is healthy only when the exact configured model is installed."""

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(
        {"models": [{"name": "batiai/gemma4-e4b:q4"}]}
    ).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        status = _local_llm_status("http://localhost:11434", "batiai/gemma4-e4b:q4")

    assert status.available is True
    assert "Ollama (batiai/gemma4-e4b:q4)" in status.message


def test_handle_skills_lists_registered_skills(registry: SkillRegistry) -> None:
    """The skills handler should list registered skill metadata."""

    registry.register(
        SkillInfo(
            name="status",
            description="System health and context",
            commands=("/status",),
            enabled=True,
            handler=dummy_handler,
        )
    )

    response = handle_skills(registry)

    assert "Registered Skills" in response
    assert "status" in response
    assert "System health and context" in response
    assert "Telegram Commands" in response
    assert "/today" in response
