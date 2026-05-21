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
