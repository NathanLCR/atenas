"""Deterministic keyword search over notes and file metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.db import get_connection
from core.knowledge.models import SearchResult


class SearchEngine:
    """Deterministic keyword search over notes and file metadata.

    Uses SQL LIKE for matching with a simple ranking system based on
    match location (title > tags > body/path). No embeddings or vector DB.
    """
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path

    def search(
        self, query: str, include_notes: bool = True, include_files: bool = True,
        module_id: str | None = None, assignment_id: str | None = None, limit: int = 20,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        if include_notes:
            results.extend(self._search_notes(query, module_id, assignment_id, limit))
        if include_files:
            results.extend(self._search_files(query, module_id, assignment_id, limit))
        results.sort(key=lambda r: (r.rank, r.updated_at), reverse=True)
        return results[:limit]

    def _search_notes(self, query: str, module_id: str | None, assignment_id: str | None, limit: int) -> list[SearchResult]:
        conditions = ["archived = 0"]
        params: list[object] = []
        if module_id: conditions.append("module_id = ?"); params.append(module_id)
        if assignment_id: conditions.append("assignment_id = ?"); params.append(assignment_id)
        where = " AND ".join(conditions)
        like = f"%{query}%"
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT id, title, body, module_id, assignment_id, tags, updated_at FROM notes
                    WHERE {where} AND (LOWER(title) LIKE LOWER(?) OR LOWER(body) LIKE LOWER(?) OR LOWER(tags) LIKE LOWER(?))
                    ORDER BY updated_at DESC LIMIT ?""",
                params + [like, like, like, limit],
            ).fetchall()
        results = []
        for row in rows:
            rank = self._rank_note(row, query)
            snippet = self._make_snippet(row["body"], query)
            results.append(SearchResult(
                kind="note", id=row["id"], title=row["title"], snippet=snippet,
                module_id=row["module_id"], assignment_id=row["assignment_id"],
                updated_at=row["updated_at"], rank=rank,
            ))
        return results

    def _search_files(self, query: str, module_id: str | None, assignment_id: str | None, limit: int) -> list[SearchResult]:
        conditions = ["archived = 0"]
        params: list[object] = []
        if module_id: conditions.append("module_id = ?"); params.append(module_id)
        if assignment_id: conditions.append("assignment_id = ?"); params.append(assignment_id)
        where = " AND ".join(conditions)
        like = f"%{query}%"
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT id, filename, title, path, description, module_id, assignment_id, tags, updated_at FROM files
                    WHERE {where} AND (LOWER(filename) LIKE LOWER(?) OR LOWER(COALESCE(title, '')) LIKE LOWER(?)
                    OR LOWER(path) LIKE LOWER(?) OR LOWER(COALESCE(description, '')) LIKE LOWER(?) OR LOWER(tags) LIKE LOWER(?))
                    ORDER BY updated_at DESC LIMIT ?""",
                params + [like, like, like, like, like, limit],
            ).fetchall()
        results = []
        for row in rows:
            rank = self._rank_file(row, query)
            snippet = self._make_file_snippet(row, query)
            results.append(SearchResult(
                kind="file", id=row["id"], title=row["title"] or row["filename"], snippet=snippet,
                module_id=row["module_id"], assignment_id=row["assignment_id"],
                updated_at=row["updated_at"], rank=rank,
            ))
        return results

    def _rank_note(self, row: sqlite3.Row, query: str) -> int:
        q = query.lower()
        title = (row["title"] or "").lower()
        tags = (row["tags"] or "").lower()
        if title == q: return 100
        if q in title: return 80
        if q in tags: return 60
        return 40

    def _rank_file(self, row: sqlite3.Row, query: str) -> int:
        q = query.lower()
        title = (row["title"] or "").lower()
        filename = (row["filename"] or "").lower()
        tags = (row["tags"] or "").lower()
        if title == q or filename == q: return 100
        if q in title or q in filename: return 80
        if q in tags: return 60
        return 40

    def _make_snippet(self, body: str, query: str, max_len: int = 160) -> str:
        if not body: return ""
        idx = body.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(body), idx + len(query) + 80)
            snippet = body[start:end].strip()
            if start > 0: snippet = "..." + snippet
            if end < len(body): snippet = snippet + "..."
            return snippet
        return body[:max_len]

    def _make_file_snippet(self, row: sqlite3.Row, query: str, max_len: int = 160) -> str:
        desc = row["description"] or ""
        if desc: return self._make_snippet(desc, query, max_len)
        return (row["path"] or "")[:max_len]
