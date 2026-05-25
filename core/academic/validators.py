"""Deterministic parsing and validation utilities for Phase 5 input commands."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from core.schemas import FatigueLevel

WEEKDAY_MAP: dict[str, int] = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1, "tues": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3, "thurs": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

ALLOWED_STATUSES = {"todo", "in_progress", "submitted", "done", "cancelled"}

_KV_TOKEN_RE = re.compile(r'(\w+)=(?:"([^"]*?)"|(\S+))')


@dataclass(frozen=True)
class ValidationResult:
    """Structured result for validation operations."""

    success: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommandResult:
    """Structured result for service command operations."""

    success: bool
    message: str
    record_id: str | None = None
    errors: list[str] = field(default_factory=list)


def parse_kv_args(text: str) -> dict[str, str]:
    """Parse key=value and key=\"quoted value\" pairs from command text.

    Supports both quoted and unquoted values. Keys are lowercased.
    Used by all Telegram command handlers for argument parsing.
    """
    args: dict[str, str] = {}
    for match in _KV_TOKEN_RE.finditer(text):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3)
        args[key] = value
    return args


def parse_weekday(value: str | int) -> int | None:
    """Parse weekday from integer 0-6 or alias string. Returns None if invalid."""
    if isinstance(value, int):
        return value if 0 <= value <= 6 else None
    if isinstance(value, str):
        return WEEKDAY_MAP.get(value.strip().lower())
    return None


def parse_date_only(value: str, tz: ZoneInfo) -> date | None:
    """Parse YYYY-MM-DD into a date. Returns None if invalid."""
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def parse_datetime_input(value: str, tz: ZoneInfo) -> tuple[datetime | None, str | None]:
    """Parse datetime from supported formats.

    Accepted:
        YYYY-MM-DD
        YYYY-MM-DD HH:MM
        YYYY-MM-DDTHH:MM
        YYYY-MM-DD HH:MM:SS
        YYYY-MM-DDTHH:MM:SS

    Returns (datetime, error_message).
    Date-only values become 23:59 local time.
    """
    value = value.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=tz), None
        except ValueError:
            continue

    date_only = parse_date_only(value, tz)
    if date_only is not None:
        return datetime.combine(date_only, time(23, 59), tzinfo=tz), None

    return None, f"Invalid datetime: {value}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"


def parse_datetime_strict(value: str, tz: ZoneInfo) -> tuple[datetime | None, str | None]:
    """Parse datetime requiring time component. Date-only is rejected.

    Returns (datetime, error_message).
    """
    value = value.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=tz), None
        except ValueError:
            continue

    if len(value) == 10:
        try:
            date.fromisoformat(value)
            return None, "Date-only not allowed for work shifts. Use YYYY-MM-DD HH:MM"
        except ValueError:
            pass

    return None, f"Invalid datetime: {value}. Use YYYY-MM-DD HH:MM"


def validate_status(value: str) -> str | None:
    """Normalize and validate assignment status. Returns None if invalid."""
    normalized = value.strip().lower()
    return normalized if normalized in ALLOWED_STATUSES else None


def validate_priority(value: str | int) -> int | None:
    """Validate priority 1-5. Returns None if invalid."""
    try:
        p = int(value)
        return p if 1 <= p <= 5 else None
    except (ValueError, TypeError):
        return None


def validate_hours(value: str | float | int) -> float | None:
    """Validate hours >= 0 and <= 1000. Returns None if invalid."""
    try:
        h = float(value)
        if h < 0 or h > 1000:
            return None
        return h
    except (ValueError, TypeError):
        return None


def validate_weight(value: str | float | int) -> float | None:
    """Validate weight >= 0 and <= 100. Returns None if invalid."""
    try:
        w = float(value)
        if w < 0 or w > 100:
            return None
        return w
    except (ValueError, TypeError):
        return None


def validate_energy_cost(value: str | int) -> int | None:
    """Validate energy_cost 1-5. Returns None if invalid."""
    try:
        e = int(value)
        return e if 1 <= e <= 5 else None
    except (ValueError, TypeError):
        return None


def validate_fatigue_level(value: str | FatigueLevel) -> FatigueLevel | None:
    """Normalize a work-shift fatigue level. Returns None if invalid."""
    if isinstance(value, FatigueLevel):
        return value
    try:
        return FatigueLevel(str(value).strip().lower())
    except (ValueError, TypeError):
        return None


def validate_text_field(value: str | None, max_length: int = 200, required: bool = False) -> str | None:
    """Trim and validate a text field. Returns None if empty/invalid."""
    if value is None:
        return None if not required else ""
    trimmed = value.strip()
    if required and not trimmed:
        return ""
    if len(trimmed) > max_length:
        return None
    return trimmed


def validate_notes(value: str | None, max_length: int = 2000) -> str | None:
    """Trim and validate notes field."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > max_length:
        return None
    return trimmed
