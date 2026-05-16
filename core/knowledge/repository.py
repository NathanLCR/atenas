"""SQLite repository for knowledge layer data (notes, files, links)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.db import get_connection
from core.knowledge.models import FileRecord, Note, NoteFileLink
from core.knowledge.validators import deserialize_tags, serialize_tags
from core.time import utc_now_iso


class KnowledgeRepository:
    """SQLite persistence layer for notes, files, and note-file links.

    Handles all SQL operations. Tags are serialized as comma-separated
    strings. IDs are INTEGER AUTOINCREMENT (distinct from academic UUIDs).
    """
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path

    def create_note(self, note: Note) -> Note:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO notes (
                    title, body, module_id, assignment_id, source_type, tags,
                    archived, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (note.title, note.body, note.module_id, note.assignment_id,
                 note.source_type, serialize_tags(note.tags),
                 note.created_at, note.updated_at),
            )
            conn.commit()
            return note.model_copy(update={"id": cursor.lastrowid})

    def get_note(self, note_id: int) -> Note | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return None
        return self._note_from_row(row)

    def list_notes(
        self, module_id: str | None = None, assignment_id: str | None = None,
        tag: str | None = None, source_type: str | None = None,
        limit: int = 20, include_archived: bool = False,
    ) -> list[Note]:
        conditions = []
        params: list[object] = []
        if not include_archived:
            conditions.append("archived = 0")
        if module_id:
            conditions.append("module_id = ?"); params.append(module_id)
        if assignment_id:
            conditions.append("assignment_id = ?"); params.append(assignment_id)
        if tag:
            conditions.append("tags LIKE ?"); params.append(f"%{tag}%")
        if source_type:
            conditions.append("source_type = ?"); params.append(source_type)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM notes {where} ORDER BY updated_at DESC LIMIT ?", params,
            ).fetchall()
        return [self._note_from_row(r) for r in rows]

    def update_note(
        self, note_id: int, title: str | None = None, body: str | None = None,
        module_id: str | None = None, assignment_id: str | None = None,
        source_type: str | None = None, tags: list[str] | None = None,
    ) -> Note | None:
        existing = self.get_note(note_id)
        if existing is None:
            return None
        updates: dict[str, object] = {}
        if title is not None: updates["title"] = title
        if body is not None: updates["body"] = body
        if module_id is not None: updates["module_id"] = module_id
        if assignment_id is not None: updates["assignment_id"] = assignment_id
        if source_type is not None: updates["source_type"] = source_type
        if tags is not None: updates["tags"] = serialize_tags(tags)
        if not updates:
            return existing
        updates["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [note_id]
        with get_connection(self.db_path) as conn:
            conn.execute(f"UPDATE notes SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return self.get_note(note_id)

    def archive_note(self, note_id: int) -> bool:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE notes SET archived = 1, updated_at = ? WHERE id = ?",
                (utc_now_iso(), note_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def create_file(self, file_record: FileRecord) -> FileRecord:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO files (
                    path, filename, title, description, module_id, assignment_id,
                    file_type, mime_type, size_bytes, sha256, tags, archived,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (file_record.path, file_record.filename, file_record.title,
                 file_record.description, file_record.module_id, file_record.assignment_id,
                 file_record.file_type, file_record.mime_type, file_record.size_bytes,
                 file_record.sha256, serialize_tags(file_record.tags),
                 file_record.created_at, file_record.updated_at),
            )
            conn.commit()
            return file_record.model_copy(update={"id": cursor.lastrowid})

    def get_file(self, file_id: int) -> FileRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if row is None:
            return None
        return self._file_from_row(row)

    def list_files(
        self, module_id: str | None = None, assignment_id: str | None = None,
        tag: str | None = None, limit: int = 20, include_archived: bool = False,
    ) -> list[FileRecord]:
        conditions = []
        params: list[object] = []
        if not include_archived:
            conditions.append("archived = 0")
        if module_id:
            conditions.append("module_id = ?"); params.append(module_id)
        if assignment_id:
            conditions.append("assignment_id = ?"); params.append(assignment_id)
        if tag:
            conditions.append("tags LIKE ?"); params.append(f"%{tag}%")
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM files {where} ORDER BY updated_at DESC LIMIT ?", params,
            ).fetchall()
        return [self._file_from_row(r) for r in rows]

    def archive_file(self, file_id: int) -> bool:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE files SET archived = 1, updated_at = ? WHERE id = ?",
                (utc_now_iso(), file_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def find_duplicate_file(self, path: str) -> FileRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE path = ? AND archived = 0", (path,),
            ).fetchone()
        if row is None:
            return None
        return self._file_from_row(row)

    def link_note_file(self, link: NoteFileLink) -> NoteFileLink | None:
        with get_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO note_file_links (note_id, file_id, created_at) VALUES (?, ?, ?)",
                    (link.note_id, link.file_id, link.created_at),
                )
                conn.commit()
                return link.model_copy(update={"id": cursor.lastrowid})
            except sqlite3.IntegrityError:
                conn.rollback()
                return None

    def get_linked_files(self, note_id: int) -> list[FileRecord]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """SELECT f.* FROM files f JOIN note_file_links nfl ON f.id = nfl.file_id
                   WHERE nfl.note_id = ? AND f.archived = 0 ORDER BY f.updated_at DESC""",
                (note_id,),
            ).fetchall()
        return [self._file_from_row(r) for r in rows]

    def get_linked_notes(self, file_id: int) -> list[Note]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """SELECT n.* FROM notes n JOIN note_file_links nfl ON n.id = nfl.note_id
                   WHERE nfl.file_id = ? AND n.archived = 0 ORDER BY n.updated_at DESC""",
                (file_id,),
            ).fetchall()
        return [self._note_from_row(r) for r in rows]

    def _note_from_row(self, row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"], title=row["title"], body=row["body"],
            module_id=row["module_id"], assignment_id=row["assignment_id"],
            source_type=row["source_type"], tags=deserialize_tags(row["tags"]),
            archived=bool(row["archived"]), created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _file_from_row(self, row: sqlite3.Row) -> FileRecord:
        return FileRecord(
            id=row["id"], path=row["path"], filename=row["filename"],
            title=row["title"], description=row["description"],
            module_id=row["module_id"], assignment_id=row["assignment_id"],
            file_type=row["file_type"], mime_type=row["mime_type"],
            size_bytes=row["size_bytes"], sha256=row["sha256"],
            tags=deserialize_tags(row["tags"]), archived=bool(row["archived"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
