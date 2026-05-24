"""Service layer for knowledge operations (notes, files, search)."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.repository import AcademicRepository
from core.knowledge.models import CommandResult, FileRecord, Note, NoteFileLink, SearchResult
from core.knowledge.repository import KnowledgeRepository
from core.knowledge.search import SearchEngine
from core.knowledge.validators import (
    derive_file_type, derive_mime_type, normalize_tags,
    validate_note_body, validate_note_title, validate_source_type,
)
from core.path_policy import PathPolicy, PathPolicyError
from core.time import utc_now_iso


class KnowledgeService:
    """Business logic for notes, files, and search operations.

    Validates inputs, checks module/assignment existence via the academic
    repository, and delegates persistence to KnowledgeRepository.
    """

    def __init__(
        self,
        db_path: Path | str,
        timezone: str | ZoneInfo = "Europe/Dublin",
        allowed_file_roots: list[Path | str] | None = None,
    ) -> None:
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
        self.repository = KnowledgeRepository(db_path)
        self.search_engine = SearchEngine(db_path)
        self._academic_repo = AcademicRepository(db_path, self.timezone)
        self._path_policy = PathPolicy(allowed_file_roots or [Path("inbox"), Path("memory")])

    def create_note(self, title: str, body: str, module_id: str | None = None,
                    assignment_id: str | None = None, source_type: str = "manual",
                    tags: list[str] | None = None) -> CommandResult:
        validated_title = validate_note_title(title)
        if not validated_title:
            return CommandResult(success=False, message="Note title is required.")
        if validated_title is None:
            return CommandResult(success=False, message="Note title exceeds 200 characters.")
        validated_body = validate_note_body(body)
        if not validated_body:
            return CommandResult(success=False, message="Note body is required.")
        if validated_body is None:
            return CommandResult(success=False, message="Note body exceeds 20000 characters.")
        if module_id:
            if self._academic_repo.get_module_by_id(module_id) is None:
                return CommandResult(success=False, message=f"Module #{module_id} not found.")
        if assignment_id:
            if self._academic_repo.get_assignment_by_id(assignment_id) is None:
                return CommandResult(success=False, message=f"Assignment #{assignment_id} not found.")
        validated_source = validate_source_type(source_type)
        if validated_source is None:
            return CommandResult(success=False, message=f"Invalid source_type.")
        normalized_tags = normalize_tags(tags)
        note = Note(title=validated_title, body=validated_body, module_id=module_id,
                    assignment_id=assignment_id, source_type=validated_source, tags=normalized_tags)
        created = self.repository.create_note(note)
        tags_label = f"\nTags: {', '.join(normalized_tags)}" if normalized_tags else ""
        return CommandResult(success=True, message=f"Note added\n\n#{created.id} \u2014 {created.title}{tags_label}", record_id=created.id)

    def get_note(self, note_id: int) -> Note | None:
        return self.repository.get_note(note_id)

    def list_notes(self, module_id: str | None = None, assignment_id: str | None = None,
                   tag: str | None = None, source_type: str | None = None, limit: int = 20) -> list[Note]:
        return self.repository.list_notes(module_id=module_id, assignment_id=assignment_id,
                                          tag=tag, source_type=source_type, limit=limit)

    def update_note(self, note_id: int, title: str | None = None, body: str | None = None,
                    module_id: str | None = None, assignment_id: str | None = None,
                    source_type: str | None = None, tags: list[str] | None = None) -> CommandResult:
        existing = self.repository.get_note(note_id)
        if existing is None:
            return CommandResult(success=False, message=f"Note #{note_id} not found.")
        if title is not None:
            v = validate_note_title(title)
            if not v: return CommandResult(success=False, message="Note title is required.")
            if v is None: return CommandResult(success=False, message="Note title exceeds 200 characters.")
            title = v
        if body is not None:
            v = validate_note_body(body)
            if not v: return CommandResult(success=False, message="Note body is required.")
            if v is None: return CommandResult(success=False, message="Note body exceeds 20000 characters.")
            body = v
        if source_type is not None:
            if validate_source_type(source_type) is None:
                return CommandResult(success=False, message="Invalid source_type.")
        if module_id and self._academic_repo.get_module_by_id(module_id) is None:
            return CommandResult(success=False, message=f"Module #{module_id} not found.")
        if assignment_id and self._academic_repo.get_assignment_by_id(assignment_id) is None:
            return CommandResult(success=False, message=f"Assignment #{assignment_id} not found.")
        normalized_tags = normalize_tags(tags) if tags is not None else None
        updated = self.repository.update_note(note_id=note_id, title=title, body=body,
                                               module_id=module_id, assignment_id=assignment_id,
                                               source_type=source_type, tags=normalized_tags)
        if updated is None:
            return CommandResult(success=False, message="Failed to update note.")
        return CommandResult(success=True, message=f"Note updated\n\n#{note_id} \u2014 {updated.title}")

    def archive_note(self, note_id: int) -> CommandResult:
        existing = self.repository.get_note(note_id)
        if existing is None:
            return CommandResult(success=False, message=f"Note #{note_id} not found.")
        self.repository.archive_note(note_id)
        return CommandResult(success=True, message=f"Note archived\n\n#{note_id} \u2014 {existing.title}")

    def register_file(self, path: str, title: str | None = None, description: str | None = None,
                      module_id: str | None = None, assignment_id: str | None = None,
                      tags: list[str] | None = None, allow_missing: bool = False) -> CommandResult:
        """Register a local file's metadata.

        Registered files must exist and pass the canonical filesystem policy.
        """
        if not path or not path.strip():
            return CommandResult(success=False, message="File path is required.")
        path = path.strip()
        try:
            resolved_path = self._path_policy.validate_registered_file(path)
        except PathPolicyError as exc:
            return CommandResult(success=False, message=str(exc))

        path = str(resolved_path)
        file_path = resolved_path
        existing = self.repository.find_duplicate_file(path)
        if existing is not None:
            return CommandResult(success=False, message=f"File already registered\n\n#{existing.id} \u2014 {existing.title or existing.filename}")
        filename = file_path.name
        file_type = derive_file_type(path)
        mime_type = derive_mime_type(path)
        size_bytes = None
        if file_path.exists():
            try: size_bytes = file_path.stat().st_size
            except OSError: pass
        if module_id and self._academic_repo.get_module_by_id(module_id) is None:
            return CommandResult(success=False, message=f"Module #{module_id} not found.")
        if assignment_id and self._academic_repo.get_assignment_by_id(assignment_id) is None:
            return CommandResult(success=False, message=f"Assignment #{assignment_id} not found.")
        normalized_tags = normalize_tags(tags)
        record = FileRecord(path=path, filename=filename, title=title, description=description,
                            module_id=module_id, assignment_id=assignment_id, file_type=file_type,
                            mime_type=mime_type, size_bytes=size_bytes, tags=normalized_tags)
        created = self.repository.create_file(record)
        type_label = f"\nType: {file_type}" if file_type else ""
        tags_label = f"\nTags: {', '.join(normalized_tags)}" if normalized_tags else ""
        return CommandResult(success=True, message=f"File registered\n\n#{created.id} \u2014 {created.title or created.filename}{type_label}{tags_label}", record_id=created.id)

    def get_file(self, file_id: int) -> FileRecord | None:
        return self.repository.get_file(file_id)

    def list_files(self, module_id: str | None = None, assignment_id: str | None = None,
                   tag: str | None = None, limit: int = 20) -> list[FileRecord]:
        return self.repository.list_files(module_id=module_id, assignment_id=assignment_id, tag=tag, limit=limit)

    def archive_file(self, file_id: int) -> CommandResult:
        existing = self.repository.get_file(file_id)
        if existing is None:
            return CommandResult(success=False, message=f"File #{file_id} not found.")
        self.repository.archive_file(file_id)
        return CommandResult(success=True, message=f"File archived\n\n#{file_id} \u2014 {existing.title or existing.filename}")

    def link_note_file(self, note_id: int, file_id: int) -> CommandResult:
        if self.repository.get_note(note_id) is None:
            return CommandResult(success=False, message=f"Note #{note_id} not found.")
        if self.repository.get_file(file_id) is None:
            return CommandResult(success=False, message=f"File #{file_id} not found.")
        link = NoteFileLink(note_id=note_id, file_id=file_id, created_at=utc_now_iso())
        result = self.repository.link_note_file(link)
        if result is None:
            return CommandResult(success=False, message="Link already exists.")
        return CommandResult(success=True, message=f"Linked note #{note_id} to file #{file_id}.")

    def search(self, query: str, include_notes: bool = True, include_files: bool = True,
               module_id: str | None = None, assignment_id: str | None = None, limit: int = 20) -> tuple[list[SearchResult], str | None]:
        """Search notes and files by keyword.

        Returns (results, error). Query must be at least 2 characters.
        Archived records are excluded from results.
        """
        if not query or len(query.strip()) < 2:
            return [], "Search query must be at least 2 characters."
        query = query.strip()
        results = self.search_engine.search(query=query, include_notes=include_notes, include_files=include_files,
                                             module_id=module_id, assignment_id=assignment_id, limit=limit)
        if not results:
            return [], f'No notes or files found for: "{query}"'
        return results, None
