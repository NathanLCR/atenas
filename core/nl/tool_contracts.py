"""Contracts shared by the Atenas NL tool registry and agent loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from core.academic.validators import CommandResult
from core.schemas import (
    ActionOutcome,
    ActionProposal,
    ActionResult,
    ActionTier,
    FatigueLevel,
    StrictModel,
)


class ToolCategory(StrEnum):
    """Tool categories visible to the LLM."""

    READ = "read"
    COMPUTE = "compute"
    ACT = "act"
    SYSTEM = "system"
    WEB = "web"


class EmptyArgs(StrictModel):
    """Tool with no arguments."""


class ListAssignmentsArgs(StrictModel):
    """Arguments for assignment listing."""

    include_completed: bool = False
    query: str | None = None


class SearchNotesArgs(StrictModel):
    """Arguments for local note/file keyword search."""

    query: str = Field(min_length=2)
    limit: int = Field(default=5, ge=1, le=10)


class RetrieveSourcesArgs(StrictModel):
    """Arguments for controlled local retrieval."""

    question: str = Field(min_length=2)
    limit: int = Field(default=5, ge=1, le=10)
    include_files: bool = True


class SetAssignmentStatusArgs(StrictModel):
    """Arguments for updating assignment status."""

    assignment: str = Field(min_length=1, description="Assignment ID, ID prefix, or exact title")
    status: str = Field(min_length=1, description="todo, in_progress, submitted, done, or cancelled")


class SetAssignmentHoursArgs(StrictModel):
    """Arguments for updating assignment completed hours."""

    assignment: str = Field(min_length=1, description="Assignment ID, ID prefix, or exact title")
    completed_hours: float = Field(ge=0, description="Completed hours (non-negative)")


class ModuleDeleteArgs(StrictModel):
    """Arguments for deleting unreferenced modules."""

    module_ids: list[str] = Field(min_length=1)


class DeduplicateModuleGroupArgs(StrictModel):
    """One duplicate-module merge operation."""

    canonical_module_id: str = Field(min_length=1)
    duplicate_module_ids: list[str] = Field(min_length=1)


class DeduplicateModulesArgs(StrictModel):
    """Arguments for merging duplicate module records."""

    groups: list[DeduplicateModuleGroupArgs] = Field(min_length=1)


class ArchiveNoteArgs(StrictModel):
    """Arguments for archiving a single note."""

    note: str = Field(min_length=1, description="Note ID or exact title")


class WebSearchArgs(StrictModel):
    """Arguments for a guarded web search/fetch."""

    query: str = Field(min_length=2, description="Search query — no sensitive records")


class ReadMemoryArgs(StrictModel):
    """Arguments for reading persistent memory items."""

    domain: str | None = Field(
        default=None,
        description="Filter by domain: studies, work, assignments, papers, projects, preferences, archive",
    )
    topic: str | None = Field(default=None, description="Partial topic match")
    tag: str | None = Field(default=None, description="Filter by tag")
    importance: str | None = Field(default=None, description="Filter: low, medium, high, critical")
    inferred: bool | None = Field(default=None, description="Filter: true=inferred, false=stated")
    limit: int = Field(default=10, ge=1, le=50)


class WriteMemoryArgs(StrictModel):
    """Arguments for writing a persistent memory item."""

    content: str = Field(min_length=1, max_length=5000, description="Full memory content")
    summary: str = Field(min_length=1, max_length=2000, description="Concise summary")
    domain: str = Field(description="Domain: studies, work, assignments, papers, projects, preferences, archive")
    topic: str = Field(min_length=1, max_length=100, description="Topic label")
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: str = Field(default="medium", description="Importance: low, medium, high, critical")
    inferred: bool = Field(default=True, description="True if model-inferred, false if user-stated")
    sensitive: bool = Field(default=False, description="True if the memory contains sensitive info")


class UpdateMemoryArgs(StrictModel):
    """Arguments for updating an existing memory item."""

    memory_id: str = Field(min_length=1, description="Memory item ID to update")
    content: str | None = Field(default=None, description="New content")
    summary: str | None = Field(default=None, description="New summary")
    topic: str | None = Field(default=None, description="New topic")
    tags: list[str] | None = Field(default=None, description="New tags")
    importance: str | None = Field(default=None, description="New importance: low, medium, high, critical")


class DeadlinesArgs(StrictModel):
    """Arguments for listing upcoming deadlines."""

    limit: int = Field(default=10, ge=1, le=50)


class AvailabilityArgs(StrictModel):
    """Arguments for checking availability."""

    start_date: str | None = Field(default=None, description="Start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="End date YYYY-MM-DD")


class ListClassSessionsArgs(StrictModel):
    """Arguments for listing class sessions."""

    active_only: bool = True


class ListWorkShiftsArgs(StrictModel):
    """Arguments for listing work shifts."""

    limit: int = Field(default=30, ge=1, le=100)


class GenerateStudyPlanArgs(StrictModel):
    """Arguments for generating a study plan."""

    horizon_days: int = Field(default=7, ge=1, le=30)
    reference_date: str | None = Field(default=None, description="Reference date YYYY-MM-DD")


class AddAssignmentArgs(StrictModel):
    """Arguments for adding an assignment."""

    title: str = Field(min_length=1, max_length=200)
    due_at: str = Field(min_length=1, description="Due date YYYY-MM-DD or YYYY-MM-DD HH:MM")
    module_id: str | None = Field(default=None, description="Module ID or title")
    priority: int = Field(default=3, ge=1, le=5, description="Priority 1-5")
    estimated_hours: float | None = Field(default=None, ge=0.5, le=200)


class AddNoteArgs(StrictModel):
    """Arguments for creating a note."""

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    module_id: str | None = Field(default=None, description="Module ID or title")
    tags: list[str] = Field(default_factory=list, max_length=10)


class AddClassSessionArgs(StrictModel):
    """Arguments for adding a class session."""

    title: str = Field(min_length=1, max_length=200)
    weekday: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: str = Field(min_length=1, description="HH:MM")
    end_time: str = Field(min_length=1, description="HH:MM")
    module_id: str | None = Field(default=None, description="Module ID or title")
    location: str | None = Field(default=None, max_length=200)


class AddWorkShiftArgs(StrictModel):
    """Arguments for adding a work shift."""

    title: str = Field(min_length=1, max_length=200, description="Workplace name")
    start_at: str = Field(min_length=1, description="YYYY-MM-DD HH:MM")
    end_at: str = Field(min_length=1, description="YYYY-MM-DD HH:MM")
    location: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    energy_cost: int | None = Field(default=None, ge=1, le=5, description="Energy cost 1-5")
    fatigue_level: FatigueLevel = Field(
        default=FatigueLevel.MEDIUM,
        description="Work-shift fatigue level: low, medium, or high",
    )


class StructuredToolResult(StrictModel):
    """Structured result returned by every tool."""

    ok: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    executed: bool = False
    pending: bool = False


class PendingToolAction(StrictModel):
    """Pending confirm-first action stored outside the LLM."""

    tool_name: str
    proposal: ActionProposal
    confirmation_message: str


@dataclass(frozen=True)
class ToolRun:
    """Internal result plus optional pending action."""

    result: StructuredToolResult
    pending_action: PendingToolAction | None = None


ToolHandler = Callable[[BaseModel, int | None], ToolRun]


@dataclass(frozen=True)
class ToolDefinition:
    """A single LLM-callable Atenas tool."""

    name: str
    description: str
    category: ToolCategory
    args_schema: type[BaseModel]
    result_schema: type[StructuredToolResult]
    handler: ToolHandler
    action_tier: ActionTier | None = None

    def schema_for_llm(self) -> dict[str, Any]:
        """Return the schema that may be shown to the LLM."""

        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": self.args_schema.model_json_schema(),
            "returns": self.result_schema.model_json_schema(),
        }
        if self.action_tier is not None:
            payload["action_tier"] = self.action_tier.value
        return payload


def typed(model: BaseModel, typ: type[BaseModel]):
    """Return a validated model instance of the expected concrete type."""

    return model if isinstance(model, typ) else typ.model_validate(model.model_dump())


def done(message: str, *, data: dict[str, Any] | None = None, ok: bool = True) -> ToolRun:
    """Build a non-pending tool run."""

    return ToolRun(
        StructuredToolResult(ok=ok, message=message, data=data or {}),
    )


def tool_error(message: str) -> ToolRun:
    """Build a failed non-mutating tool result."""

    return done(message, ok=False)


def action_tool_run(result: ActionResult) -> ToolRun:
    """Convert an action executor result into a tool run."""

    return ToolRun(action_tool_result(result))


def action_tool_result(result: ActionResult) -> StructuredToolResult:
    """Convert an action executor result into a structured tool result."""

    return StructuredToolResult(
        ok=result.success,
        message=result.message,
        data={"action_type": result.action_type, **result.payload},
        executed=result.outcome == ActionOutcome.SUCCESS,
    )


def command_action_result(action_type: str, result: CommandResult) -> ActionResult:
    """Convert service command results into action executor results."""

    return ActionResult(
        action_type=action_type,
        outcome=ActionOutcome.SUCCESS if result.success else ActionOutcome.ERROR,
        message=result.message,
        payload={"record_id": result.record_id} if result.record_id else {},
    )


def module_data(module) -> dict[str, Any]:
    """Serialize a study module for tool results."""

    return {
        "id": module.id,
        "short_id": module.id[:8],
        "name": module.name,
        "code": module.code,
        "lecturer": module.lecturer,
    }


def assignment_data(assignment) -> dict[str, Any]:
    """Serialize an assignment for tool results."""

    return {
        "id": assignment.id,
        "short_id": assignment.id[:8],
        "title": assignment.title,
        "status": assignment.status.value,
        "due_at": assignment.due_at.isoformat(),
        "estimated_hours": assignment.estimated_hours,
        "completed_hours": assignment.completed_hours,
    }


def code_label(code: str | None) -> str:
    """Return a compact module code label."""

    return f" ({code})" if code else ""


def confirm_delete_modules(modules: list) -> str:
    """Build a confirmation message for direct module deletion."""

    lines = ["Delete modules?", ""]
    lines.extend(f"- #{module.id[:8]} {module.name}{code_label(module.code)}" for module in modules)
    lines.extend(["", 'Reply "yes" to confirm or "no" to cancel.'])
    return "\n".join(lines)


def confirm_deduplicate_modules(groups: list[tuple[Any, list[Any]]]) -> str:
    """Build a confirmation message for module deduplication."""

    lines = ["Delete duplicate modules?", ""]
    for canonical, duplicates in groups:
        lines.append(f"Keep: #{canonical.id[:8]} {canonical.name}{code_label(canonical.code)}")
        for duplicate in duplicates:
            lines.append(f"Delete/merge: #{duplicate.id[:8]} {duplicate.name}{code_label(duplicate.code)}")
        lines.append("")
    lines.append('Reply "yes" to confirm or "no" to cancel.')
    return "\n".join(lines).rstrip()


def safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload metadata safe to expose in a tool observation."""

    return {
        key: value
        for key, value in payload.items()
        if key not in {"body", "content", "notes"}
    }


def wrap_web_content(url: str, content: str, max_length: int = 4000) -> str:
    """Wrap fetched web content as untrusted data delimiters."""

    snippet = content[:max_length]
    if len(content) > max_length:
        snippet += "... (truncated)"
    return f'<web url="{url}">{snippet}</web>'
