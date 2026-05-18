"""Models for controlled retrieval and source-grounded answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NO_SOURCE_FALLBACK = "I do not have enough information in your registered notes/files to answer this."

SourceKind = Literal["note", "file"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrievalChunk(StrictModel):
    source_kind: SourceKind
    source_id: int
    chunk_index: int = Field(ge=0)
    title: str
    text: str = Field(min_length=1)
    module_id: str | None = None
    assignment_id: str | None = None
    updated_at: str = ""

    @property
    def source_label(self) -> str:
        prefix = "N" if self.source_kind == "note" else "F"
        return f"{prefix}{self.source_id}"

    @property
    def chunk_label(self) -> str:
        return f"{self.source_label}.{self.chunk_index + 1}"


class RetrievedSource(RetrievalChunk):
    score: float = 0.0
    snippet: str = ""


class RetrievalAnswer(StrictModel):
    success: bool
    question: str
    answer: str = ""
    sources: list[RetrievedSource] = Field(default_factory=list)
    model: str | None = None
    error: str | None = None


class RetrievalIndexStats(StrictModel):
    notes_indexed: int = 0
    files_indexed: int = 0
    chunks_indexed: int = 0
    skipped_files: int = 0
