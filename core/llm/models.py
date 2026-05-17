"""Models for local LLM assistance actions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMActionResult:
    """Result of a local LLM action on a note or file."""

    success: bool
    action: str
    source_kind: str
    source_id: int
    output: str = ""
    model: str | None = None
    error: str | None = None


LLM_ACTIONS = frozenset({
    "summarize",
    "explain",
    "questions",
    "flashcards",
    "rewrite",
})

REWRITE_STYLES = frozenset({
    "concise",
    "detailed",
    "simple",
    "academic",
    "bullet-points",
})
