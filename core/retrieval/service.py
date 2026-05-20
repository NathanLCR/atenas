"""Service layer for controlled retrieval over registered notes and files."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from core.knowledge.models import FileRecord, Note
from core.knowledge.repository import KnowledgeRepository
from core.llm.client import OllamaClient
from core.retrieval.chunking import chunk_text
from core.retrieval.embeddings import query_terms
from core.retrieval.models import (
    NO_SOURCE_FALLBACK,
    RetrievalAnswer,
    RetrievalChunk,
    RetrievalIndexStats,
    RetrievedSource,
)
from core.retrieval.prompts import build_answer_prompt
from core.retrieval.vector_store import RetrievalVectorStore

MAX_FILE_CHARS = 120_000
MAX_INDEX_RECORDS = 10_000
TEXT_SUFFIXES = frozenset({
    ".css",
    ".csv",
    ".html",
    ".ipynb",
    ".js",
    ".json",
    ".md",
    ".py",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
})


class RetrievalService:
    """Controlled RAG foundation over explicitly registered knowledge records."""

    def __init__(
        self,
        db_path: Path | str,
        timezone: str | ZoneInfo = "Europe/Dublin",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1:8b",
        ollama_timeout: int = 60,
    ) -> None:
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
        self.repository = KnowledgeRepository(db_path)
        self.store = RetrievalVectorStore(db_path)
        self.client = OllamaClient(
            base_url=ollama_base_url,
            model=ollama_model,
            timeout=ollama_timeout,
        )

    def rebuild_index(self, *, include_files: bool = True) -> RetrievalIndexStats:
        """Rebuild the retrieval index from non-archived registered records."""

        chunks: list[RetrievalChunk] = []
        notes_indexed = 0
        files_indexed = 0
        skipped_files = 0

        for note in self.repository.list_notes(limit=MAX_INDEX_RECORDS):
            note_chunks = self._chunks_for_note(note)
            if note_chunks:
                notes_indexed += 1
                chunks.extend(note_chunks)

        if include_files:
            for file_record in self.repository.list_files(limit=MAX_INDEX_RECORDS):
                file_chunks = self._chunks_for_file(file_record)
                if file_chunks:
                    files_indexed += 1
                    chunks.extend(file_chunks)
                else:
                    skipped_files += 1

        self.store.rebuild(chunks)
        return RetrievalIndexStats(
            notes_indexed=notes_indexed,
            files_indexed=files_indexed,
            chunks_indexed=len(chunks),
            skipped_files=skipped_files,
        )

    def sync_index(self, *, include_files: bool = True) -> RetrievalIndexStats:
        """Incrementally sync stale registered records into the retrieval index."""

        notes_indexed = 0
        files_indexed = 0
        chunks_indexed = 0
        skipped_files = 0
        active_sources: set[tuple[str, int]] = set()

        for note in self.repository.list_notes(limit=MAX_INDEX_RECORDS):
            if note.id is None:
                continue
            active_sources.add(("note", note.id))
            note_chunks = self._chunks_for_note(note)
            if not note_chunks:
                continue
            notes_indexed += 1
            if not self.store.source_is_current(
                "note",
                note.id,
                updated_at=note.updated_at,
                chunk_count=len(note_chunks),
            ):
                chunks_indexed += self.store.replace_source(note_chunks)

        source_kinds = {"note"}
        if include_files:
            source_kinds.add("file")
            for file_record in self.repository.list_files(limit=MAX_INDEX_RECORDS):
                if file_record.id is None:
                    continue
                file_chunks = self._chunks_for_file(file_record)
                if file_chunks:
                    active_sources.add(("file", file_record.id))
                    files_indexed += 1
                    if not self.store.source_is_current(
                        "file",
                        file_record.id,
                        updated_at=file_record.updated_at,
                        chunk_count=len(file_chunks),
                    ):
                        chunks_indexed += self.store.replace_source(file_chunks)
                else:
                    skipped_files += 1

        self.store.delete_stale_sources(
            active_sources,
            source_kinds=frozenset(source_kinds),
        )
        return RetrievalIndexStats(
            notes_indexed=notes_indexed,
            files_indexed=files_indexed,
            chunks_indexed=chunks_indexed,
            skipped_files=skipped_files,
        )

    def retrieve_sources(
        self,
        question: str,
        *,
        note_id: int | None = None,
        module_id: str | None = None,
        assignment_id: str | None = None,
        limit: int = 5,
        include_files: bool = True,
    ) -> tuple[list[RetrievedSource], str | None]:
        """Return relevant sources for a question without generating an answer."""

        question = question.strip()
        error = self._validate_question(question)
        if error:
            return [], error
        note_error = self._validate_note_scope(note_id)
        if note_error:
            return [], note_error

        self.sync_index(include_files=include_files)
        source_kind = "note" if note_id is not None or not include_files else None
        sources = self.store.query(
            question,
            source_kind=source_kind,
            source_id=note_id,
            module_id=module_id,
            assignment_id=assignment_id,
            limit=limit,
        )
        return sources, None

    def answer_question(
        self,
        question: str,
        *,
        note_id: int | None = None,
        module_id: str | None = None,
        assignment_id: str | None = None,
        max_sources: int = 5,
        include_files: bool = True,
    ) -> RetrievalAnswer:
        """Answer a question using only retrieved registered sources."""

        question = question.strip()
        error = self._validate_question(question)
        if error:
            return RetrievalAnswer(success=False, question=question, error=error)

        sources, source_error = self.retrieve_sources(
            question,
            note_id=note_id,
            module_id=module_id,
            assignment_id=assignment_id,
            limit=max_sources,
            include_files=include_files,
        )
        if source_error:
            return RetrievalAnswer(success=False, question=question, error=source_error)
        if not sources:
            return RetrievalAnswer(
                success=True,
                question=question,
                answer=NO_SOURCE_FALLBACK,
                sources=[],
            )

        prompt = build_answer_prompt(question, sources)
        try:
            response = self.client.generate(prompt)
        except (ConnectionError, TimeoutError, OSError) as exc:
            return RetrievalAnswer(
                success=False,
                question=question,
                sources=sources,
                error=str(exc),
            )

        answer = response.text.strip()
        if not answer:
            return RetrievalAnswer(
                success=False,
                question=question,
                sources=sources,
                model=response.model,
                error="Local LLM returned an empty answer.",
            )
        return RetrievalAnswer(
            success=True,
            question=question,
            answer=answer,
            sources=sources,
            model=response.model,
        )

    def _chunks_for_note(self, note: Note) -> list[RetrievalChunk]:
        if note.id is None or note.archived:
            return []
        return [
            RetrievalChunk(
                source_kind="note",
                source_id=note.id,
                chunk_index=index,
                title=note.title,
                text=text,
                module_id=note.module_id,
                assignment_id=note.assignment_id,
                updated_at=note.updated_at,
            )
            for index, text in enumerate(chunk_text(note.body))
        ]

    def _chunks_for_file(self, file_record: FileRecord) -> list[RetrievalChunk]:
        if file_record.id is None or file_record.archived:
            return []
        text = self._read_registered_text_file(file_record)
        if not text:
            return []
        title = file_record.title or file_record.filename
        return [
            RetrievalChunk(
                source_kind="file",
                source_id=file_record.id,
                chunk_index=index,
                title=title,
                text=chunk,
                module_id=file_record.module_id,
                assignment_id=file_record.assignment_id,
                updated_at=file_record.updated_at,
            )
            for index, chunk in enumerate(chunk_text(text))
        ]

    def _read_registered_text_file(self, file_record: FileRecord) -> str | None:
        if not _is_text_file_record(file_record):
            return None
        path = Path(file_record.path).expanduser()
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                return handle.read(MAX_FILE_CHARS)
        except UnicodeDecodeError:
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    return handle.read(MAX_FILE_CHARS)
            except OSError:
                return None
        except OSError:
            return None

    def _validate_question(self, question: str) -> str | None:
        if len(question) < 2:
            return "Question must be at least 2 characters."
        if not query_terms(question):
            return "Question needs at least one searchable term."
        return None

    def _validate_note_scope(self, note_id: int | None) -> str | None:
        if note_id is None:
            return None
        note = self.repository.get_note(note_id)
        if note is None:
            return f"Note #{note_id} not found."
        if note.archived:
            return f"Note #{note_id} is archived."
        return None


def _is_text_file_record(file_record: FileRecord) -> bool:
    suffix = Path(file_record.path).suffix.lower()
    mime_type = (file_record.mime_type or "").lower()
    if suffix in TEXT_SUFFIXES:
        return True
    return mime_type.startswith("text/")
