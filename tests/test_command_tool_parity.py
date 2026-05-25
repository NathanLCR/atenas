"""Slash-command to agent-tool parity audit tests."""

from __future__ import annotations

from core.command_catalog import COMMAND_GROUPS, COMMAND_TOOL_PARITY
from core.nl.tools import ToolRegistry


def test_every_catalog_command_has_parity_audit_entry() -> None:
    catalog_commands = {
        command
        for _, commands in COMMAND_GROUPS
        for command in commands
    }

    assert set(COMMAND_TOOL_PARITY) == catalog_commands


def test_tool_backed_parity_entries_reference_registered_tools(tmp_db) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    tool_names = {tool.name for tool in registry.list_tools()}

    for command, entry in COMMAND_TOOL_PARITY.items():
        agent_tool = entry.get("agent_tool")
        command_only_reason = entry.get("command_only_reason")

        assert bool(agent_tool) != bool(command_only_reason), command
        if agent_tool is not None:
            assert agent_tool in tool_names, command
        else:
            assert command_only_reason and len(command_only_reason) >= 20, command
