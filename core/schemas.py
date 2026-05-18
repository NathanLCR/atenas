"""Canonical Pydantic schemas for Atenas Core."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from core.utils import utc_now

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
TIME_PATTERN = r"^\d{2}:\d{2}$"


def new_id() -> str:
    """Return a UUID4 string for TEXT primary keys."""

    return str(uuid4())


class StrictModel(BaseModel):
    """Base model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class FatigueLevel(StrEnum):
    """Work shift fatigue level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StudyIntensity(StrEnum):
    """Study block intensity level."""

    RECOVERY = "recovery"
    LIGHT = "light"
    MEDIUM = "medium"
    DEEP = "deep"


class PlanCapacity(StrEnum):
    """Overall daily plan capacity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    """Task workflow status."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class AssignmentStatus(StrEnum):
    """Assignment workflow status."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    """Priority values shared by tasks and assignments."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryDomain(StrEnum):
    """Memory item domain classification."""

    STUDIES = "studies"
    WORK = "work"
    ASSIGNMENTS = "assignments"
    PAPERS = "papers"
    PROJECTS = "projects"
    PREFERENCES = "preferences"
    ARCHIVE = "archive"


class Importance(StrEnum):
    """Memory importance level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LLMProvider(StrEnum):
    """Supported LLM provider categories."""

    LOCAL = "local"
    CLOUD = "cloud"
    MOCK = "mock"


class ActionOutcome(StrEnum):
    """Possible action and policy outcomes."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    NEEDS_CONFIRMATION = "needs_confirmation"
    ERROR = "error"


class WorkShiftItem(StrictModel):
    """Single work shift extracted from user input."""

    workplace: str | None = None
    date: str | None = Field(default=None, pattern=DATE_PATTERN)
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    role: str | None = None
    commute_minutes: int | None = Field(default=None, ge=0, le=300)
    fatigue_level: FatigueLevel = FatigueLevel.MEDIUM
    notes: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class WorkShiftsExtracted(StrictModel):
    """LLM output wrapper for one or more extracted work shifts."""

    shifts: list[WorkShiftItem]
    needs_confirmation: bool


class ClassSessionItem(StrictModel):
    """Single class session extracted from user input."""

    module_id: str | None = None
    title: str
    date: str | None = Field(default=None, pattern=DATE_PATTERN)
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    location: str | None = None
    recurrence: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ClassSessionsExtracted(StrictModel):
    """LLM output wrapper for one or more extracted class sessions."""

    sessions: list[ClassSessionItem]
    needs_confirmation: bool


class MemoryItemExtracted(StrictModel):
    """LLM output for memory extraction and classification."""

    should_store: bool
    domain: MemoryDomain
    topic: str = Field(max_length=100)
    summary: str = Field(max_length=2000)
    importance: Importance
    sensitive: bool = False
    tags: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)


class AvailabilitySlot(StrictModel):
    """Code-authored study slot. Times and the intensity cap are computed
    deterministically (availability minus hard blocks, fatigue rules). The
    LLM receives these as input and MUST NOT alter them."""

    slot_id: int = Field(ge=0)
    date: str = Field(pattern=DATE_PATTERN)
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    max_intensity: StudyIntensity


class BlockAssignment(StrictModel):
    """LLM output: what to do in one pre-computed slot. The LLM never emits
    times. `slot_id` must reference an input `AvailabilitySlot`; `intensity`
    must be <= that slot's `max_intensity`. Code validates and rejects
    assignments that violate either rule."""

    slot_id: int = Field(ge=0)
    title: str
    task_type: str | None = None
    task_id: str | None = None
    intensity: StudyIntensity
    reason: str


class DailyPlanGenerated(StrictModel):
    """LLM-generated daily plan. The LLM only assigns work to code-authored
    slots; it does not author or modify any times."""

    date: str = Field(pattern=DATE_PATTERN)
    capacity: PlanCapacity
    assignments: list[BlockAssignment]
    warnings: list[str]


class PaperMetadataExtracted(StrictModel):
    """LLM-extracted paper metadata."""

    title: str = Field(max_length=500)
    authors: list[str] = Field(min_length=1)
    year: int | None = Field(ge=1900, le=2100)
    abstract: str = Field(max_length=5000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)


class LiteratureMatrixEntry(StrictModel):
    """LLM-extracted literature matrix row."""

    paper_id: str
    research_question: str
    methodology: str
    sample: str | None = None
    key_findings: str
    limitations: str
    relevance_to_topic: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class Flashcard(StrictModel):
    """Single generated flashcard."""

    question: str
    answer: str


class FlashcardSetGenerated(StrictModel):
    """LLM-generated flashcard set."""

    topic: str
    cards: list[Flashcard]


class WorkShift(StrictModel):
    """Stored work shift record."""

    id: str = Field(default_factory=new_id)
    date: str = Field(pattern=DATE_PATTERN)
    workplace: str | None = None
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    role: str | None = None
    commute_minutes: int = Field(default=0, ge=0, le=300)
    fatigue_level: FatigueLevel = FatigueLevel.MEDIUM
    notes: str | None = None
    source: str = "telegram"
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class Assignment(StrictModel):
    """Stored assignment record."""

    id: str = Field(default_factory=new_id)
    title: str
    module_id: str | None = None
    description: str | None = None
    due_date: str | None = None
    estimated_hours: float | None = Field(default=None, ge=0)
    status: AssignmentStatus = AssignmentStatus.TODO
    priority: Priority = Priority.MEDIUM
    brief_path: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class Task(StrictModel):
    """Stored task record."""

    id: str = Field(default_factory=new_id)
    title: str
    description: str | None = None
    domain: str | None = None
    module_id: str | None = None
    assignment_id: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    estimated_minutes: int | None = Field(default=None, ge=1)
    due_date: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class MemoryItem(StrictModel):
    """Stored memory item record."""

    id: str = Field(default_factory=new_id)
    content: str
    summary: str
    domain: MemoryDomain
    topic: str
    tags: list[str] = Field(default_factory=list)
    importance: Importance = Importance.MEDIUM
    sensitive: bool = False
    source: str = "telegram"
    inferred: bool = True
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class LLMCallRecord(StrictModel):
    """Stored LLM call audit record."""

    id: str = Field(default_factory=new_id)
    provider: LLMProvider
    model: str
    task_type: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0.0)
    success: bool
    latency_ms: int | None = Field(default=None, ge=0)
    schema_valid: bool | None = None
    policy_passed: bool | None = None
    outcome: ActionOutcome = ActionOutcome.SUCCESS
    created_at: str = Field(default_factory=utc_now)


class ActionProposal(StrictModel):
    """Validated proposal passed to the policy engine.

    `user_confirmed` defaults to False so the safe path (gate the action) is
    the default. It is set True only after the user has explicitly confirmed
    (e.g. replied `yes` / `/confirm`). The LLM must never set it.
    """

    action_type: str
    payload: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    user_confirmed: bool = False
    reason: str | None = None


class ActionResult(StrictModel):
    """Result returned by the action executor."""

    id: str = Field(default_factory=new_id)
    action_type: str
    outcome: ActionOutcome
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)

    @property
    def success(self) -> bool:
        """Whether the action completed successfully."""

        return self.outcome == ActionOutcome.SUCCESS
