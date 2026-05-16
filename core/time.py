"""Deterministic time helpers for Atenas scheduling."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.config import Settings

DEFAULT_TIMEZONE = "Europe/Dublin"


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def app_timezone(settings: Settings | None = None) -> ZoneInfo:
    """Return the configured application timezone."""

    timezone_name = getattr(settings, "timezone", None) or DEFAULT_TIMEZONE
    return ZoneInfo(timezone_name)


def ensure_local_datetime(value: datetime, tz: ZoneInfo) -> datetime:
    """Interpret naive datetimes as app-local and convert aware values to app-local."""

    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def parse_local_datetime(value: str | datetime | date, tz: ZoneInfo) -> datetime:
    """Parse an ISO datetime or date into an app-local aware datetime."""

    if isinstance(value, datetime):
        return ensure_local_datetime(value, tz)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=tz)
    parsed = datetime.fromisoformat(value)
    return ensure_local_datetime(parsed, tz)


def parse_due_at(value: str | datetime | date, tz: ZoneInfo) -> datetime:
    """Parse a deadline, treating date-only values as local end-of-day."""

    if isinstance(value, datetime):
        return ensure_local_datetime(value, tz)
    if isinstance(value, date):
        return datetime.combine(value, time(23, 59), tzinfo=tz)
    if "T" not in value and len(value) == 10:
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, time(23, 59), tzinfo=tz)
    return parse_local_datetime(value, tz)


def parse_hhmm(value: str) -> time:
    """Parse HH:MM strings into a time value."""

    return time.fromisoformat(value)


def combine_local(day: date, clock: time, tz: ZoneInfo) -> datetime:
    """Combine a local date and time into an aware datetime."""

    return datetime.combine(day, clock, tzinfo=tz)


def iter_dates(start_date: date, end_date: date) -> Iterator[date]:
    """Yield all dates in an inclusive range."""

    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def week_bounds(reference_date: date) -> tuple[date, date]:
    """Return Monday-Sunday bounds for the week containing a date."""

    start = reference_date - timedelta(days=reference_date.weekday())
    return start, start + timedelta(days=6)
