"""Deterministic status skill handlers for Phase 1."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from core.db import get_connection
from core.skill_registry import SkillInfo, SkillRegistry

logger = logging.getLogger(__name__)
STATUS_DESCRIPTION = "System health and context"


def handle_ping() -> str:
    """Return a deterministic liveness response."""

    return "🏓 pong"


def handle_status(db_path: Path | str) -> str:
    """Return a formatted system status from SQLite counts."""

    counts = _load_status_counts(db_path)
    return "\n".join(
        [
            "🟢 Atenas — Online",
            "",
            "Student: Nathan",
            f"📚 Active assignments: {counts['active_assignments']}",
            f"⏰ Deadlines this week: {counts['deadlines_this_week']}",
            f"🏢 Work shifts this week: {counts['work_shifts_this_week']}",
            "💡 Local LLM: ⬜ Mock only",
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


def register_status_skill(registry: SkillRegistry, db_path: Path | str) -> None:
    """Register the status skill with `/ping`, `/status`, and `/skills`."""

    async def command_handler(command: str, args: str, user_id: int) -> str:
        if command == "/ping":
            return handle_ping()
        if command == "/status":
            return handle_status(db_path)
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


def _load_status_counts(db_path: Path | str) -> dict[str, int]:
    """Read status counts from SQLite, returning zeros if unavailable."""

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    next_week = today + timedelta(days=7)

    try:
        with get_connection(db_path) as connection:
            active_assignments = _count(
                connection,
                """
                SELECT COUNT(*) AS count
                FROM assignments
                WHERE status NOT IN ('submitted', 'graded', 'archived')
                """,
            )
            deadlines_this_week = _count(
                connection,
                """
                SELECT COUNT(*) AS count
                FROM assignments
                WHERE due_date IS NOT NULL
                  AND substr(due_date, 1, 10) BETWEEN ? AND ?
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

