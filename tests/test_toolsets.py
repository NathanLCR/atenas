"""Tests for named NL toolsets."""

from __future__ import annotations

from pathlib import Path

from core.nl.tool_contracts import ToolCategory
from core.nl.toolsets import (
    ToolsetName,
    all_toolset_tool_names,
    tool_names_for_toolsets,
    toolsets_for_telegram_message,
)
from core.nl.tools import ToolRegistry


def test_every_registered_tool_belongs_to_at_least_one_toolset(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    registered = {tool.name for tool in registry.list_tools()}

    assert registered <= all_toolset_tool_names()


def test_tui_and_dashboard_toolsets_are_readonly(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)

    for toolset in (ToolsetName.TUI_READONLY, ToolsetName.DASHBOARD_READONLY):
        tools = registry.list_tools_for_toolsets({toolset})
        unsafe = [
            tool.name
            for tool in tools
            if tool.category in {ToolCategory.ACT, ToolCategory.WEB}
        ]

        assert unsafe == []


def test_telegram_safe_excludes_web_search_even_when_web_is_enabled() -> None:
    names = tool_names_for_toolsets(
        {ToolsetName.TELEGRAM_SAFE},
        web_enabled=True,
    )

    assert "web_search" not in names


def test_telegram_egress_includes_web_search_only_when_web_is_enabled() -> None:
    enabled = tool_names_for_toolsets(
        {ToolsetName.TELEGRAM_EGRESS},
        web_enabled=True,
    )
    disabled = tool_names_for_toolsets(
        {ToolsetName.TELEGRAM_EGRESS},
        web_enabled=False,
    )

    assert "web_search" in enabled
    assert "web_search" not in disabled


def test_telegram_destructive_includes_confirm_first_destructive_tools() -> None:
    names = tool_names_for_toolsets(
        {ToolsetName.TELEGRAM_DESTRUCTIVE},
        web_enabled=True,
    )

    assert {
        "delete_modules",
        "deduplicate_modules",
        "archive_note",
        "update_memory",
    } <= names
    assert "web_search" not in names


def test_egress_and_destructive_toolsets_are_not_in_safe_default() -> None:
    names = tool_names_for_toolsets(
        {ToolsetName.TELEGRAM_SAFE},
        web_enabled=True,
    )

    assert {
        "web_search",
        "delete_modules",
        "deduplicate_modules",
        "archive_note",
        "update_memory",
    }.isdisjoint(names)


def test_registry_lists_toolsets_in_deterministic_name_order(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    tools = registry.list_tools_for_toolsets(
        {ToolsetName.TELEGRAM_SAFE, ToolsetName.TELEGRAM_EGRESS}
    )
    names = [tool.name for tool in tools]

    assert names == sorted(names)


def test_telegram_message_toolsets_stay_safe_by_default() -> None:
    assert toolsets_for_telegram_message(
        "what should I study today?",
        web_enabled=True,
    ) == {ToolsetName.TELEGRAM_SAFE}


def test_telegram_message_toolsets_add_destructive_for_explicit_request() -> None:
    assert ToolsetName.TELEGRAM_DESTRUCTIVE in toolsets_for_telegram_message(
        "delete duplicate modules",
        web_enabled=False,
    )


def test_telegram_message_toolsets_add_egress_only_when_web_is_enabled() -> None:
    enabled = toolsets_for_telegram_message("search the web", web_enabled=True)
    disabled = toolsets_for_telegram_message("search the web", web_enabled=False)

    assert ToolsetName.TELEGRAM_EGRESS in enabled
    assert ToolsetName.TELEGRAM_EGRESS not in disabled
