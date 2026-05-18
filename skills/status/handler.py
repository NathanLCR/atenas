"""Status skill handlers."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.db import get_connection
from core.skill_registry import SkillInfo, SkillRegistry

logger = logging.getLogger(__name__)
STATUS_DESCRIPTION = "System health and context"


def handle_ping() -> str:
    """Return a deterministic liveness response."""

    return "🏓 pong"


def handle_status(
    db_path: Path | str,
    timezone: str = "UTC",
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "llama3.1:8b",
) -> str:
    """Return a formatted system status from SQLite counts."""

    counts = _load_status_counts(db_path, timezone)
    llm_line = _local_llm_status(ollama_base_url, ollama_model)
    return "\n".join(
        [
            "🟢 Atenas — Online",
            "",
            "Student: Local profile",
            f"📚 Active assignments: {counts['active_assignments']}",
            f"⏰ Deadlines this week: {counts['deadlines_this_week']}",
            f"🏢 Work shifts this week: {counts['work_shifts_this_week']}",
            f"💡 Local LLM: {llm_line}",
            "☁️  Cloud LLM: ⬜ Disabled",
        ]
    )


def handle_skills(registry: SkillRegistry) -> str:
    """Return a formatted list of registered skills."""

    lines = ["📦 Registered Skills"]
    skills = sorted(registry.list_all(), key=lambda item: item.name)
    if not skills:
        lines.append("No skills registered")
        return "\n".join(lines)
    for skill in skills:
        icon = "✅" if skill.enabled else "⬜"
        lines.append(f"{icon} {skill.name:<12} — {skill.description}")
    return "\n".join(lines)


def get_status() -> str:
    """Return formatted status using process settings."""

    from app.config import get_settings

    settings = get_settings()
    return handle_status(
        settings.db_path,
        settings.timezone,
        settings.ollama_base_url,
        settings.ollama_model,
    )


def get_skills() -> str:
    """Return formatted skills using the process registry."""

    from core.skill_registry import get_registry

    return handle_skills(get_registry())


def register_status_skill(
    registry: SkillRegistry,
    db_path: Path | str,
    timezone: str = "UTC",
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "llama3.1:8b",
) -> None:
    """Register the status skill with `/ping`, `/status`, and `/skills`."""

    async def command_handler(command: str, args: str, user_id: int) -> str:
        if command == "/ping":
            return handle_ping()
        if command == "/status":
            return handle_status(db_path, timezone, ollama_base_url, ollama_model)
        if command == "/skills":
            return handle_skills(registry)
        return f"Unknown status command: {command}"

    registry.register(
        SkillInfo(
            name="status",
            description=STATUS_DESCRIPTION,
            commands=("/ping", "/status", "/skills"),
            enabled=True,
            handler=command_handler,
        )
    )
    logger.info(
        "status_skill_registered",
        extra={"event_type": "status_skill_registered"},
    )


def _load_status_counts(db_path: Path | str, timezone: str = "UTC") -> dict[str, int]:
    """Read status counts from SQLite, returning zeros if unavailable.

    The day/week window is resolved in the configured IANA ``timezone`` so
    deadline math respects NFR-07 instead of the server's local clock.
    """

    today = datetime.now(ZoneInfo(timezone)).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    next_week = today + timedelta(days=7)

    try:
        with contextlib.closing(get_connection(db_path)) as connection:
            active_assignments = _count(
                connection,
                """
                SELECT COUNT(*) AS count
                FROM assignments
                WHERE status NOT IN ('submitted', 'graded', 'archived', 'done', 'cancelled')
                """,
            )
            deadlines_this_week = _count(
                connection,
                """
                SELECT COUNT(*) AS count
                FROM assignments
                WHERE COALESCE(due_at, due_date) IS NOT NULL
                  AND substr(COALESCE(due_at, due_date), 1, 10) BETWEEN ? AND ?
                """,
                (today.isoformat(), next_week.isoformat()),
            )
            work_shifts_this_week = _count(
                connection,
                """
                SELECT COUNT(*) AS count
                FROM work_shifts
                WHERE date BETWEEN ? AND ?
                """,
                (week_start.isoformat(), week_end.isoformat()),
            )
    except sqlite3.Error as exc:
        logger.exception(
            "status_counts_failed",
            extra={"event_type": "status_counts_failed", "db_path": str(db_path)},
        )
        return {
            "active_assignments": 0,
            "deadlines_this_week": 0,
            "work_shifts_this_week": 0,
        }

    return {
        "active_assignments": active_assignments,
        "deadlines_this_week": deadlines_this_week,
        "work_shifts_this_week": work_shifts_this_week,
    }


def _count(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[str, ...] = (),
) -> int:
    """Return the integer count for a COUNT(*) query."""

    row = connection.execute(query, parameters).fetchone()
    return int(row["count"]) if row else 0


def _local_llm_status(base_url: str, model: str) -> str:
    """Return a short status string for the local Ollama LLM."""

    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return f"✅ Ollama ({model})"
    except Exception:
        pass
    return f"⬜ Ollama offline — model: {model}"
