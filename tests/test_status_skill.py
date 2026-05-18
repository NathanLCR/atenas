"""Tests for the deterministic status skill."""

from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import pytest

from core.skill_registry import SkillInfo, SkillRegistry
from skills.status.handler import handle_ping, handle_skills, handle_status


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

