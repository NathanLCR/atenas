"""Notification models for deadline alerts, study reminders, and overdue checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DeadlineAlert:
    """Upcoming assignment deadline alert."""

    assignment_id: str
    title: str
    due_at: datetime
    hours_remaining: float
    priority: int
    module_name: str | None = None

    def format_message(self) -> str:
        days = int(self.hours_remaining // 24)
        hours = int(self.hours_remaining % 24)
        if days > 0:
            time_str = f"{days}d {hours}h" if hours else f"{days}d"
        else:
            time_str = f"{int(self.hours_remaining)}h"
        prefix = f"[{self.module_name}] " if self.module_name else ""
        label = _priority_label(self.priority)
        return f"Deadline in {time_str}: {prefix}{self.title} ({label})"


@dataclass(frozen=True)
class StudyBlockReminder:
    """Upcoming study block reminder."""

    assignment_id: str
    assignment_title: str
    start_at: datetime
    minutes: int
    module_name: str | None = None

    def format_message(self) -> str:
        time_str = self.start_at.strftime("%H:%M")
        prefix = f"[{self.module_name}] " if self.module_name else ""
        return f"Study block at {time_str}: {prefix}{self.assignment_title} ({self.minutes}min)"


@dataclass(frozen=True)
class OverdueAlert:
    """Assignment that has passed its deadline without being submitted."""

    assignment_id: str
    title: str
    due_at: datetime
    hours_overdue: float
    module_name: str | None = None

    def format_message(self) -> str:
        days = int(self.hours_overdue // 24)
        hours = int(self.hours_overdue % 24)
        time_str = f"{days}d {hours}h" if days > 0 else f"{int(self.hours_overdue)}h"
        prefix = f"[{self.module_name}] " if self.module_name else ""
        return f"OVERDUE by {time_str}: {prefix}{self.title}"


def _priority_label(priority: int) -> str:
    labels = {1: "low", 2: "medium", 3: "normal", 4: "high", 5: "critical"}
    return labels.get(priority, "normal")
