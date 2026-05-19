"""Slot extraction and normalization utilities for natural language intents."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAY_MAP: dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

PRIORITY_MAP: dict[str, str] = {
    "low": "1",
    "normal": "3",
    "medium": "3",
    "high": "5",
    "urgent": "5",
}

STATUS_MAP: dict[str, str] = {
    "done": "done",
    "complete": "done",
    "finished": "done",
    "in progress": "in_progress",
    "started": "in_progress",
    "working on it": "in_progress",
    "submitted": "submitted",
    "handed in": "submitted",
    "todo": "todo",
    "not started": "todo",
    "cancelled": "cancelled",
}

NOTE_ACTION_MAP: dict[str, str] = {
    "summarise": "summarize",
    "summarize": "summarize",
    "summary": "summarize",
    "explain": "explain",
    "explanation": "explain",
    "questions": "questions",
    "question": "questions",
    "flashcards": "flashcards",
    "flashcard": "flashcards",
    "rewrite": "rewrite",
}


def normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in PRIORITY_MAP:
        return PRIORITY_MAP[normalized]
    if normalized.isdigit() and 1 <= int(normalized) <= 5:
        return normalized
    return "3"


def normalize_status(value: str) -> str | None:
    normalized = value.strip().lower()
    return STATUS_MAP.get(normalized)


def normalize_note_action(value: str) -> str | None:
    normalized = value.strip().lower()
    return NOTE_ACTION_MAP.get(normalized)


def resolve_relative_date(value: str, tz: ZoneInfo) -> str | None:
    now = datetime.now(tz)
    lower = value.strip().lower()

    if lower == "today":
        return now.strftime("%Y-%m-%d 23:59")
    if lower == "tomorrow":
        return (now + timedelta(days=1)).strftime("%Y-%m-%d 23:59")

    weekday_match = re.match(
        r"^(next\s+)?(monday|mon|tuesday|tue|tues|wednesday|wed|thursday|thu|thurs|friday|fri|saturday|sat|sunday|sun)",
        lower,
    )
    if weekday_match:
        is_next = "next" in (weekday_match.group(1) or "")
        day_name = weekday_match.group(2)
        target_weekday = WEEKDAY_MAP[day_name]
        current_weekday = now.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0 or is_next:
            days_ahead += 7
        target = now + timedelta(days=days_ahead)

        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or "0")
            ampm = time_match.group(3)
            if ampm:
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            return target.strftime(f"%Y-%m-%d {hour:02d}:{minute:02d}")
        return target.strftime("%Y-%m-%d 23:59")

    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}):(\d{2}))?", lower)
    if iso_match:
        date_part = iso_match.group(1)
        time_part = iso_match.group(2)
        minute_part = iso_match.group(3)
        if time_part:
            return f"{date_part} {int(time_part):02d}:{minute_part or '00'}"
        return f"{date_part} 23:59"

    return None


def extract_slots(slots: dict[str, str], tz: ZoneInfo) -> dict[str, str]:
    normalized: dict[str, str] = {}

    for key, value in slots.items():
        if key == "priority":
            normalized[key] = normalize_priority(value)
        elif key == "status":
            result = normalize_status(value)
            if result:
                normalized[key] = result
        elif key == "action":
            result = normalize_note_action(value)
            if result:
                normalized[key] = result
        elif key == "due_at":
            resolved = resolve_relative_date(value, tz)
            normalized[key] = resolved if resolved else value
        else:
            normalized[key] = value

    return normalized
