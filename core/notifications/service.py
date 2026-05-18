"""Notification service: computes reminders from academic data at a given timestamp."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.models import AssignmentStatus
from core.academic.service import AcademicService
from core.notifications.models import DeadlineAlert, OverdueAlert, StudyBlockReminder

_ACTIVE_STATUSES = frozenset({AssignmentStatus.TODO, AssignmentStatus.IN_PROGRESS})


class NotificationService:
    """Computes which notifications should fire given a timestamp.

    Purely deterministic — no asyncio, no scheduling. The caller is
    responsible for deciding *when* to invoke these methods.
    """

    def __init__(
        self,
        db_path: Path | str,
        timezone: str | ZoneInfo = "Europe/Dublin",
    ) -> None:
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
        self._academic = AcademicService(db_path, self.timezone)

    def deadline_alerts(
        self,
        now: datetime | None = None,
        alert_hours: int = 72,
    ) -> list[DeadlineAlert]:
        """Return alerts for active assignments due within alert_hours from now."""

        now_local = self._now(now)
        assignments = self._academic.list_upcoming_assignments(limit=200, include_completed=False)
        alerts: list[DeadlineAlert] = []
        for assignment in assignments:
            if assignment.status not in _ACTIVE_STATUSES:
                continue
            hours_remaining = (assignment.due_at - now_local).total_seconds() / 3600
            if 0 <= hours_remaining <= alert_hours:
                alerts.append(
                    DeadlineAlert(
                        assignment_id=assignment.id,
                        title=assignment.title,
                        due_at=assignment.due_at,
                        hours_remaining=hours_remaining,
                        priority=assignment.priority,
                        module_name=self._module_name(assignment.module_id),
                    )
                )
        return sorted(alerts, key=lambda a: a.hours_remaining)

    def study_block_reminder(
        self,
        now: datetime | None = None,
        lookahead_minutes: int = 30,
        min_minutes_ahead: int = 10,
    ) -> StudyBlockReminder | None:
        """Return a reminder if the next study block starts within the lookahead window."""

        now_local = self._now(now)
        block = self._academic.get_next_study_recommendation(now=now_local)
        if block is None:
            return None
        minutes_until = (block.start_at - now_local).total_seconds() / 60
        if min_minutes_ahead <= minutes_until <= lookahead_minutes:
            return StudyBlockReminder(
                assignment_id=block.assignment_id,
                assignment_title=block.assignment_title,
                start_at=block.start_at,
                minutes=block.minutes,
                module_name=block.module_name,
            )
        return None

    def overdue_alerts(self, now: datetime | None = None) -> list[OverdueAlert]:
        """Return alerts for active assignments whose deadline has passed."""

        now_local = self._now(now)
        assignments = self._academic.list_upcoming_assignments(limit=200, include_completed=False)
        alerts: list[OverdueAlert] = []
        for assignment in assignments:
            if assignment.status not in _ACTIVE_STATUSES:
                continue
            if assignment.due_at < now_local:
                hours_overdue = (now_local - assignment.due_at).total_seconds() / 3600
                alerts.append(
                    OverdueAlert(
                        assignment_id=assignment.id,
                        title=assignment.title,
                        due_at=assignment.due_at,
                        hours_overdue=hours_overdue,
                        module_name=self._module_name(assignment.module_id),
                    )
                )
        return sorted(alerts, key=lambda a: a.hours_overdue, reverse=True)

    def weekly_review_message(self, now: datetime | None = None) -> str:
        """Return a weekly review summary message."""

        now_local = self._now(now)
        overview = self._academic.get_week_overview(now=now_local)
        n = overview.open_deadline_count
        if n > 0:
            return (
                f"Weekly review: {n} deadline(s) this week. "
                f"Type /week for your schedule and /plan for study recommendations."
            )
        return "Weekly review: no deadlines this week. Type /week for your schedule."

    def format_deadline_alerts_message(
        self,
        now: datetime | None = None,
        alert_hours: int = 72,
    ) -> str:
        """Format deadline alerts as a Telegram message, or empty string if none."""

        alerts = self.deadline_alerts(now=now, alert_hours=alert_hours)
        if not alerts:
            return ""
        lines = [f"Deadline alert ({len(alerts)} upcoming):"]
        for alert in alerts:
            lines.append(f"  {alert.format_message()}")
        return "\n".join(lines)

    def format_overdue_message(self, now: datetime | None = None) -> str:
        """Format overdue alerts as a Telegram message, or empty string if none."""

        alerts = self.overdue_alerts(now=now)
        if not alerts:
            return ""
        lines = [f"Overdue assignments ({len(alerts)}):"]
        for alert in alerts:
            lines.append(f"  {alert.format_message()}")
        return "\n".join(lines)

    def _now(self, now: datetime | None) -> datetime:
        return now if now is not None else datetime.now(self.timezone)

    def _module_name(self, module_id: str | None) -> str | None:
        if module_id is None:
            return None
        for module in self._academic.list_modules():
            if module.id == module_id:
                return module.name
        return None


def seconds_until(target_hour: int, target_minute: int, now: datetime) -> float:
    """Return seconds from now until the next occurrence of HH:MM in now's timezone."""

    candidate = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return (candidate - now).total_seconds()


def seconds_until_weekday(weekday: int, hour: int, minute: int, now: datetime) -> float:
    """Return seconds from now until the next occurrence of weekday at HH:MM.

    weekday follows Python convention: 0=Monday ... 6=Sunday.
    """

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    if days_ahead == 0 and candidate <= now:
        days_ahead = 7
    candidate += timedelta(days=days_ahead)
    return (candidate - now).total_seconds()
