"""Shared Atenas command catalog."""

from __future__ import annotations

COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Core", ("/start", "/help", "/ping", "/status", "/skills", "/pending", "/cancel_pending", "/confirm")),
    ("Schedule", ("/today", "/week", "/deadlines", "/availability", "/plan", "/study")),
    (
        "Data",
        (
            "/add_module",
            "/add_class",
            "/add_shift",
            "/add_assignment",
            "/set_status",
            "/set_hours",
        ),
    ),
    ("Lists", ("/modules", "/classes", "/shifts", "/assignments", "/reminders")),
    (
        "Notes/files",
        (
            "/add_note",
            "/notes",
            "/note",
            "/archive_note",
            "/add_file",
            "/files",
            "/search",
            "/link_note_file",
        ),
    ),
    ("Retrieval", ("/ask_notes", "/ask_note", "/sources")),
    (
        "LLM note tools",
        (
            "/summarize_note",
            "/explain_note",
            "/questions_note",
            "/flashcards_note",
            "/rewrite_note",
        ),
    ),
)

COMMAND_DESCRIPTIONS: dict[str, str] = {
    "/start": "Welcome and quick start",
    "/help": "List all commands",
    "/ping": "Check the bot is alive",
    "/status": "System status",
    "/skills": "Command catalog",
    "/pending": "Show the action awaiting confirmation",
    "/cancel_pending": "Cancel the pending action",
    "/confirm": "Confirm the pending action",
    "/today": "Today's classes, shifts and deadlines",
    "/week": "This week's overview",
    "/deadlines": "Upcoming deadlines",
    "/availability": "Free study time",
    "/plan": "Generate a study plan",
    "/study": "Suggest what to study next",
    "/add_module": "Add a module",
    "/add_class": "Add a class session",
    "/add_shift": "Add a work shift",
    "/add_assignment": "Add an assignment",
    "/set_status": "Set assignment status",
    "/set_hours": "Set assignment hours",
    "/modules": "List modules",
    "/classes": "List classes",
    "/shifts": "List work shifts",
    "/assignments": "List assignments",
    "/reminders": "Review reminders",
    "/add_note": "Save a note",
    "/notes": "List or search notes",
    "/note": "Show one note",
    "/archive_note": "Archive a note",
    "/add_file": "Register a file by server path",
    "/files": "List registered files",
    "/search": "Search notes",
    "/link_note_file": "Link a note to a file",
    "/ask_notes": "Ask a question about your notes",
    "/ask_note": "Ask a question about one note",
    "/sources": "Show matching sources",
    "/summarize_note": "Summarize a note",
    "/explain_note": "Explain a note",
    "/questions_note": "Practice questions from a note",
    "/flashcards_note": "Flashcards from a note",
    "/rewrite_note": "Rewrite a note",
}

COMMAND_TOOL_PARITY: dict[str, dict[str, str]] = {
    "/start": {
        "command_only_reason": "Static onboarding text shown on first contact; not a stateful agent task.",
    },
    "/help": {
        "command_only_reason": "Static grouped command list generated from the catalog; not a stateful agent task.",
    },
    "/ping": {
        "command_only_reason": "Local adapter health shortcut; agent status uses get_status instead.",
    },
    "/status": {"agent_tool": "get_status"},
    "/skills": {
        "command_only_reason": "Telegram command catalog and help surface; not a stateful agent task.",
    },
    "/pending": {
        "command_only_reason": "Deterministic pending-action review shortcut backed by AgentRuntimeStore.",
    },
    "/cancel_pending": {
        "command_only_reason": "Deterministic pending-action cancellation shortcut backed by AgentRuntimeStore.",
    },
    "/confirm": {
        "command_only_reason": "Deterministic equivalent of replying 'yes' to the active pending action; backed by AgentRuntimeStore.",
    },
    "/today": {"agent_tool": "get_today_overview"},
    "/week": {"agent_tool": "get_week_overview"},
    "/deadlines": {"agent_tool": "get_deadlines"},
    "/availability": {"agent_tool": "get_availability"},
    "/plan": {"agent_tool": "generate_study_plan"},
    "/study": {"agent_tool": "suggest_next_task"},
    "/add_module": {
        "command_only_reason": "Module creation remains a deterministic v1 shortcut; agent module writes are post-v1.",
    },
    "/add_class": {"agent_tool": "add_class_session"},
    "/add_shift": {"agent_tool": "add_work_shift"},
    "/add_assignment": {"agent_tool": "add_assignment"},
    "/set_status": {"agent_tool": "set_assignment_status"},
    "/set_hours": {"agent_tool": "set_assignment_hours"},
    "/modules": {"agent_tool": "list_modules"},
    "/classes": {"agent_tool": "list_class_sessions"},
    "/shifts": {"agent_tool": "list_work_shifts"},
    "/assignments": {"agent_tool": "list_assignments"},
    "/reminders": {
        "command_only_reason": "Reminder notification review is a Telegram support shortcut with no v1 agent tool.",
    },
    "/add_note": {"agent_tool": "add_note"},
    "/notes": {"agent_tool": "search_notes"},
    "/note": {"agent_tool": "search_notes"},
    "/archive_note": {"agent_tool": "archive_note"},
    "/add_file": {
        "command_only_reason": "File registration is a local filesystem support command; unrestricted file paths are not exposed to the agent.",
    },
    "/files": {
        "command_only_reason": "Registered-file listing is a local support shortcut; retrieval uses retrieve_sources.",
    },
    "/search": {"agent_tool": "search_notes"},
    "/link_note_file": {
        "command_only_reason": "Manual note-file linking is kept command-only until file tools have a separate confirmation and path policy contract.",
    },
    "/ask_notes": {"agent_tool": "retrieve_sources"},
    "/ask_note": {"agent_tool": "retrieve_sources"},
    "/sources": {"agent_tool": "retrieve_sources"},
    "/summarize_note": {"agent_tool": "retrieve_sources"},
    "/explain_note": {"agent_tool": "retrieve_sources"},
    "/questions_note": {"agent_tool": "retrieve_sources"},
    "/flashcards_note": {"agent_tool": "retrieve_sources"},
    "/rewrite_note": {"agent_tool": "retrieve_sources"},
}


def format_command_catalog() -> str:
    """Return the Telegram command catalog shown by /skills."""

    lines = ["Telegram Commands"]
    for group, commands in COMMAND_GROUPS:
        lines.append(f"{group}: {' '.join(commands)}")
    lines.append("Natural language: send any plain message")
    return "\n".join(lines)
