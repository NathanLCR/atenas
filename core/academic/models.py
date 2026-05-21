"""Pydantic models for deterministic academic and work scheduling."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.time import parse_hhmm, utc_now_iso

TIME_PATTERN = r"^\d{2}:\d{2}$"


def new_id() -> str:
    """Return a UUID4 string for SQLite TEXT primary keys."""

    return str(uuid4())


class StrictModel(BaseModel):
    """Base model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class AssignmentStatus(StrEnum):
    """Phase 3 assignment workflow states."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    DONE = "done"
    CANCELLED = "cancelled"


class StudyModule(StrictModel):
    """Stored university module/course."""

    id: str = Field(default_factory=new_id)
    code: str | None = None
    name: str = Field(min_length=1)
    lecturer: str | None = None
    notes: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("module name is required")
        return value


class DuplicateModuleGroup(StrictModel):
    """A normalized set of duplicate study modules."""

    key: str
    canonical_module: StudyModule
    duplicate_modules: list[StudyModule]
    all_modules: list[StudyModule]


class ClassSession(StrictModel):
    """Weekly recurring class block."""

    id: str = Field(default_factory=new_id)
    module_id: str | None = None
    title: str = Field(min_length=1)
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    location: str | None = None
    recurrence: Literal["weekly"] = "weekly"
    active: bool = True
    notes: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("class title is required")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if parse_hhmm(self.start_time) >= parse_hhmm(self.end_time):
            raise ValueError("class start_time must be before end_time")
        return self


class WorkShift(StrictModel):
    """Date-specific work block."""

    id: str = Field(default_factory=new_id)
    title: str = Field(min_length=1)
    start_at: datetime
    end_at: datetime
    location: str | None = None
    role: str | None = None
    energy_cost: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("work shift title is required")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.start_at >= self.end_at:
            raise ValueError("work shift start_at must be before end_at")
        return self


class Assignment(StrictModel):
    """Coursework, exam, submission, or important academic deadline."""

    id: str = Field(default_factory=new_id)
    module_id: str | None = None
    title: str = Field(min_length=1)
    due_at: datetime
    status: AssignmentStatus = AssignmentStatus.TODO
    priority: int = Field(default=3, ge=1, le=5)
    weight: float | None = Field(default=None, ge=0)
    estimated_hours: float | None = Field(default=None, ge=0)
    completed_hours: float = Field(default=0, ge=0)
    notes: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("assignment title is required")
        return value


class TimeBlock(StrictModel):
    """Blocked time used by availability calculations."""

    title: str
    start_at: datetime
    end_at: datetime
    kind: Literal["class", "work", "assignment", "manual"]
    metadata: dict[str, object] = Field(default_factory=dict)


class StudyWindow(StrictModel):
    """A usable free study window."""

    start_at: datetime
    end_at: datetime
    minutes: int


class DayAvailability(StrictModel):
    """Blocked and free time for one local day."""

    date: date
    blocked: list[TimeBlock]
    study_windows: list[StudyWindow]
    total_study_minutes: int


class WeekAvailability(StrictModel):
    """Availability across an inclusive date range."""

    start_date: date
    end_date: date
    days: list[DayAvailability]
    total_study_minutes: int


class DaySummary(StrictModel):
    """Compact per-day summary for week views."""

    date: date
    class_minutes: int
    work_minutes: int
    study_minutes: int


class WeekOverview(StrictModel):
    """Deterministic week overview."""

    start_date: date
    end_date: date
    class_count: int
    work_shift_count: int
    open_deadline_count: int
    availability: WeekAvailability
    day_summaries: list[DaySummary]


class TodayOverview(StrictModel):
    """Deterministic today overview."""

    date: date
    classes: list[TimeBlock]
    work_shifts: list[TimeBlock]
    deadlines: list[Assignment]
    availability: DayAvailability
