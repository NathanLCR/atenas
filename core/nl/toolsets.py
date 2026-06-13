"""Named Atenas NL toolsets for surface and risk filtering."""

from __future__ import annotations

from enum import StrEnum
from typing import Iterable


class ToolsetName(StrEnum):
    """Named tool groups inspired by Hermes toolsets."""

    TELEGRAM_SAFE = "telegram-safe"
    TELEGRAM_EGRESS = "telegram-egress"
    TELEGRAM_DESTRUCTIVE = "telegram-destructive"
    TUI_READONLY = "tui-readonly"
    DASHBOARD_READONLY = "dashboard-readonly"
    DEV_LOCAL = "dev-local"


LOCAL_READ_TOOL_NAMES = frozenset(
    {
        "list_modules",
        "list_assignments",
        "search_notes",
        "retrieve_sources",
        "read_memory",
        "get_status",
        "get_today_overview",
        "get_week_overview",
        "get_deadlines",
        "get_availability",
        "list_class_sessions",
        "list_work_shifts",
        "get_local_llm_status",
    }
)

LOCAL_COMPUTE_TOOL_NAMES = frozenset(
    {
        "suggest_next_task",
        "detect_duplicate_modules",
        "generate_study_plan",
        "explain_deadline_risk",
    }
)

TELEGRAM_AUTO_ACTION_TOOL_NAMES = frozenset(
    {
        "set_assignment_status",
        "set_assignment_hours",
        "write_memory",
        "add_assignment",
        "add_note",
        "add_class_session",
        "add_work_shift",
    }
)

TELEGRAM_DESTRUCTIVE_TOOL_NAMES = frozenset(
    {
        "delete_modules",
        "deduplicate_modules",
        "archive_note",
        "update_memory",
    }
)

TELEGRAM_EGRESS_TOOL_NAMES = frozenset({"web_search"})

TOOLSET_TOOL_NAMES = {
    ToolsetName.TELEGRAM_SAFE: (
        LOCAL_READ_TOOL_NAMES
        | LOCAL_COMPUTE_TOOL_NAMES
        | TELEGRAM_AUTO_ACTION_TOOL_NAMES
    ),
    ToolsetName.TELEGRAM_EGRESS: TELEGRAM_EGRESS_TOOL_NAMES,
    ToolsetName.TELEGRAM_DESTRUCTIVE: TELEGRAM_DESTRUCTIVE_TOOL_NAMES,
    ToolsetName.TUI_READONLY: LOCAL_READ_TOOL_NAMES | LOCAL_COMPUTE_TOOL_NAMES,
    ToolsetName.DASHBOARD_READONLY: LOCAL_READ_TOOL_NAMES | LOCAL_COMPUTE_TOOL_NAMES,
    ToolsetName.DEV_LOCAL: frozenset({"get_status", "get_local_llm_status"}),
}

DESTRUCTIVE_REQUEST_MARKERS = (
    # English
    "archive",
    "clear",
    "deduplicate",
    "de-duplicate",
    "delete",
    "merge",
    "merge duplicate",
    "remove",
    # Portuguese
    "apagar",
    "arquivar",
    "deletar",
    "duplicado",
    "duplicar",
    "excluir",
    "limpar",
    "remover",
)

EGRESS_REQUEST_MARKERS = (
    # English
    "google",
    "internet",
    "look up",
    "lookup",
    "online",
    "search the web",
    "web",
    # Portuguese
    "buscar na internet",
    "buscar na web",
    "na internet",
    "online",
    "pesquisar",
)


def tool_names_for_toolsets(
    toolsets: set[ToolsetName],
    *,
    web_enabled: bool,
) -> set[str]:
    """Return visible tool names for the selected toolsets."""

    selected_toolsets = _normalize_toolsets(toolsets)
    names: set[str] = set()
    for toolset in sorted(selected_toolsets):
        names.update(TOOLSET_TOOL_NAMES[toolset])

    if not (web_enabled and ToolsetName.TELEGRAM_EGRESS in selected_toolsets):
        names.discard("web_search")
    return names


def toolsets_for_telegram_message(
    message: str,
    *,
    web_enabled: bool,
) -> set[ToolsetName]:
    """Select Telegram toolsets for a single user-authored message."""

    text = message.casefold()
    toolsets = {ToolsetName.TELEGRAM_SAFE}
    if _contains_marker(text, DESTRUCTIVE_REQUEST_MARKERS):
        toolsets.add(ToolsetName.TELEGRAM_DESTRUCTIVE)
    if web_enabled and _contains_marker(text, EGRESS_REQUEST_MARKERS):
        toolsets.add(ToolsetName.TELEGRAM_EGRESS)
    return toolsets


def all_toolset_tool_names() -> set[str]:
    """Return every tool name referenced by a declared toolset."""

    names: set[str] = set()
    for tool_names in TOOLSET_TOOL_NAMES.values():
        names.update(tool_names)
    return names


def _normalize_toolsets(toolsets: Iterable[ToolsetName]) -> set[ToolsetName]:
    return {ToolsetName(toolset) for toolset in toolsets}


def _contains_marker(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)
