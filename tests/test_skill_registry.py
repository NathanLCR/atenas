"""Tests for the skill registry."""

import pytest

from core.skill_registry import SkillInfo, SkillRegistry


async def dummy_handler(command: str, args: str, user_id: int) -> str:
    """Return a simple handler response for registry tests."""

    return f"{command}:{args}:{user_id}"


def test_register_skill_find_by_name(registry: SkillRegistry) -> None:
    """Registered skills should be retrievable by name."""

    skill = SkillInfo(
        name="status",
        description="System health",
        commands=("/status",),
        enabled=True,
        handler=dummy_handler,
    )

    registry.register(skill)

    assert registry.get_by_name("status") == skill


def test_find_skill_by_command(registry: SkillRegistry) -> None:
    """Registered commands should resolve to their skill."""

    registry.register(
        SkillInfo(
            name="status",
            description="System health",
            commands=("/status",),
            enabled=True,
            handler=dummy_handler,
        )
    )

    assert registry.get_by_command("/status").name == "status"


def test_unknown_command_returns_none(registry: SkillRegistry) -> None:
    """Unknown commands should not resolve to a skill."""

    assert registry.get_by_command("/missing") is None


def test_disabled_skill_not_returned_by_command(registry: SkillRegistry) -> None:
    """Disabled skills should remain listed but unavailable for dispatch."""

    registry.register(
        SkillInfo(
            name="status",
            description="System health",
            commands=("/status",),
            enabled=False,
            handler=dummy_handler,
        )
    )

    assert registry.get_by_name("status") is not None
    assert registry.get_by_command("/status") is None


@pytest.mark.asyncio
async def test_dispatch_calls_handler(registry: SkillRegistry) -> None:
    """Dispatch should call the enabled skill handler."""

    registry.register(
        SkillInfo(
            name="status",
            description="System health",
            commands=("/status",),
            enabled=True,
            handler=dummy_handler,
        )
    )

    assert await registry.dispatch("/status", "now", user_id=42) == "/status:now:42"

