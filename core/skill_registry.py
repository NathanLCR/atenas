"""Skill registration and command dispatch for Atenas Core."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)
SkillHandler = Callable[[str, str, int], Awaitable[str]]


@dataclass
class SkillInfo:
    """Registered skill metadata."""

    name: str
    description: str
    commands: tuple[str, ...]
    enabled: bool
    handler: SkillHandler


class SkillRegistry:
    """Registry for skill metadata and command lookup."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillInfo] = {}
        self._command_index: dict[str, str] = {}

    def register(self, skill: SkillInfo) -> None:
        """Register or replace a skill and its command mappings."""

        self._skills[skill.name] = skill
        for command, skill_name in list(self._command_index.items()):
            if skill_name == skill.name:
                del self._command_index[command]
        for command in skill.commands:
            self._command_index[command] = skill.name
        logger.info(
            "skill_registered",
            extra={
                "event_type": "skill_registered",
                "skill": skill.name,
                "commands": list(skill.commands),
                "enabled": skill.enabled,
            },
        )

    def get_by_name(self, name: str) -> SkillInfo | None:
        """Return a skill by name."""

        return self._skills.get(name)

    def get_by_command(self, command: str) -> SkillInfo | None:
        """Return the enabled skill handling a command."""

        skill_name = self._command_index.get(command)
        if skill_name is None:
            return None
        skill = self._skills.get(skill_name)
        if skill is None or not skill.enabled:
            return None
        return skill

    def list_all(self) -> list[SkillInfo]:
        """Return all registered skills."""

        return list(self._skills.values())

    def list_enabled(self) -> list[SkillInfo]:
        """Return enabled registered skills."""

        return [skill for skill in self._skills.values() if skill.enabled]

    async def dispatch(self, command: str, args: str = "", *, user_id: int) -> str:
        """Dispatch a command to its registered skill handler."""

        skill = self.get_by_command(command)
        if skill is None:
            logger.info(
                "command_executed",
                extra={
                    "event_type": "command_executed",
                    "command": command,
                    "actor_user_id": user_id,
                    "success": False,
                },
            )
            return f"Unknown command: {command}"
        try:
            result = await skill.handler(command, args, user_id)
            success = True
        except Exception:
            success = False
            raise
        finally:
            logger.info(
                "command_executed",
                extra={
                    "event_type": "command_executed",
                    "command": command,
                    "actor_user_id": user_id,
                    "success": success,
                },
            )
        return result


_registry = SkillRegistry()


def get_registry() -> SkillRegistry:
    """Return the process-wide skill registry singleton."""

    return _registry

