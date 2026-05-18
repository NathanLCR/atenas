"""Pydantic models for the knowledge layer (notes, files, search)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.time import utc_now_iso


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ALLOWED_SOURCE_TYPES = frozenset({
    "manual", "lecture", "assignment", "paper", "reading", "meeting", "other",
})


class Note(StrictModel):
    id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    module_id: str | None = None
    assignment_id: str | None = None
    source_type: str = "manual"
    tags: list[str] = Field(default_factory=list)
    archived: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        if value not in ALLOWED_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {ALLOWED_SOURCE_TYPES}")
        return value


class FileRecord(StrictModel):
    id: int | None = None
    path: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    module_id: str | None = None
    assignment_id: str | None = None
    file_type: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    tags: list[str] = Field(default_factory=list)
    archived: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class NoteFileLink(StrictModel):
    id: int | None = None
    note_id: int
    file_id: int
    created_at: str = Field(default_factory=utc_now_iso)


class SearchResult(StrictModel):
    kind: Literal["note", "file"]
    id: int
    title: str
    snippet: str
    module_id: str | None = None
    assignment_id: str | None = None
    updated_at: str = ""
    rank: int = 0


class CommandResult(StrictModel):
    success: bool
    message: str
    record_id: int | None = None
