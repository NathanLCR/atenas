"""Shared Atenas command catalog."""

from __future__ import annotations

COMMAND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Core", ("/ping", "/status", "/skills")),
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


def format_command_catalog() -> str:
    """Return the Telegram command catalog shown by /skills."""

    lines = ["Telegram Commands"]
    for group, commands in COMMAND_GROUPS:
        lines.append(f"{group}: {' '.join(commands)}")
    lines.append("Natural language: send any plain message")
    return "\n".join(lines)
