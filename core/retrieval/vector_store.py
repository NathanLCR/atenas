"""SQLite-backed retrieval chunk index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from core.db import get_connection, init_db
from core.retrieval.embeddings import lexical_score, query_terms
from core.retrieval.models import RetrievalChunk, RetrievedSource
from core.time import utc_now_iso


class RetrievalVectorStore:
    """A deterministic SQLite index for note/file text chunks.

    This MVP intentionally uses sparse lexical scoring instead of a vector DB.
    The table shape leaves a clear boundary for a later embedding-backed store.
    Schema is owned by core.db.init_db.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path
        self.ensure_schema()

    def ensure_schema(self) -> None:
        init_db(self.db_path)

    def rebuild(self, chunks: list[RetrievalChunk]) -> int:
        indexed_at = utc_now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM retrieval_chunks")
            conn.executemany(
                """
                INSERT INTO retrieval_chunks (
                    id, source_kind, source_id, chunk_index, title, text,
                    module_id, assignment_id, updated_at, indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        self._chunk_id(chunk),
                        chunk.source_kind,
                        chunk.source_id,
                        chunk.chunk_index,
                        chunk.title,
                        chunk.text,
                        chunk.module_id,
                        chunk.assignment_id,
                        chunk.updated_at,
                        indexed_at,
                    )
                    for chunk in chunks
                ],
            )
            _sync_fts(conn)
            conn.commit()
        return len(chunks)

    def source_is_current(
        self,
        source_kind: str,
        source_id: int,
        *,
        updated_at: str,
        chunk_count: int,
    ) -> bool:
        """Return whether a source's indexed chunks match its current shape."""

        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS chunk_count,
                       MIN(updated_at) AS min_updated_at,
                       MAX(updated_at) AS max_updated_at
                FROM retrieval_chunks
                WHERE source_kind = ? AND source_id = ?
                """,
                (source_kind, source_id),
            ).fetchone()
        if row is None:
            return False
        return (
            row["chunk_count"] == chunk_count
            and row["min_updated_at"] == updated_at
            and row["max_updated_at"] == updated_at
        )

    def replace_source(self, chunks: list[RetrievalChunk]) -> int:
        """Replace all indexed chunks for a single source."""

        if not chunks:
            return 0
        source_kind = chunks[0].source_kind
        source_id = chunks[0].source_id
        if any(chunk.source_kind != source_kind or chunk.source_id != source_id for chunk in chunks):
            raise ValueError("replace_source requires chunks from exactly one source")

        indexed_at = utc_now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM retrieval_chunks WHERE source_kind = ? AND source_id = ?",
                (source_kind, source_id),
            )
            conn.executemany(
                """
                INSERT INTO retrieval_chunks (
                    id, source_kind, source_id, chunk_index, title, text,
                    module_id, assignment_id, updated_at, indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        self._chunk_id(chunk),
                        chunk.source_kind,
                        chunk.source_id,
                        chunk.chunk_index,
                        chunk.title,
                        chunk.text,
                        chunk.module_id,
                        chunk.assignment_id,
                        chunk.updated_at,
                        indexed_at,
                    )
                    for chunk in chunks
                ],
            )
            _sync_fts(conn)
            conn.commit()
        return len(chunks)

    def delete_stale_sources(
        self,
        active_sources: Iterable[tuple[str, int]],
        *,
        source_kinds: frozenset[str],
    ) -> int:
        """Delete chunks for archived or removed sources."""

        active = set(active_sources)
        deleted = 0
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT source_kind, source_id
                FROM retrieval_chunks
                ORDER BY source_kind, source_id
                """
            ).fetchall()
            for row in rows:
                key = (row["source_kind"], row["source_id"])
                if row["source_kind"] in source_kinds and key not in active:
                    cursor = conn.execute(
                        "DELETE FROM retrieval_chunks WHERE source_kind = ? AND source_id = ?",
                        key,
                    )
                    deleted += cursor.rowcount
            _sync_fts(conn)
            conn.commit()
        return deleted

    def count(self) -> int:
        with get_connection(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) AS count FROM retrieval_chunks").fetchone()["count"])

    def _fts_available(self) -> bool:
        """Check if FTS5 is available and the virtual table exists."""
        try:
            with get_connection(self.db_path) as conn:
                conn.execute("SELECT count(*) FROM retrieval_chunks_fts").fetchone()
            return True
        except sqlite3.OperationalError:
            return False

    def _fts_query(
        self,
        question: str,
        *,
        source_kind: str | None = None,
        source_id: int | None = None,
        module_id: str | None = None,
        assignment_id: str | None = None,
        limit: int = 5,
    ) -> list[RetrievedSource] | None:
        """Query via FTS5/BM25. Returns None if FTS is unavailable or query fails."""
        if not query_terms(question):
            return []
        if not self._fts_available():
            return None

        sanitized = " OR ".join(
            term.replace('"', "").replace("'", "")
            for term in query_terms(question)
            if term
        )
        if not sanitized.strip():
            return None

        conditions: list[str] = ["retrieval_chunks_fts MATCH ?"]
        params: list[object] = [sanitized]
        if source_kind:
            conditions.append("rc.source_kind = ?")
            params.append(source_kind)
        if source_id is not None:
            conditions.append("rc.source_id = ?")
            params.append(source_id)
        if module_id:
            conditions.append("rc.module_id = ?")
            params.append(module_id)
        if assignment_id:
            conditions.append("rc.assignment_id = ?")
            params.append(assignment_id)

        where = " AND ".join(conditions)
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT rc.source_kind, rc.source_id, rc.chunk_index,
                           rc.title, rc.text, rc.module_id, rc.assignment_id,
                           rc.updated_at,
                           bm25(retrieval_chunks_fts, 0.0, 10.0, 5.0) AS bm25_score
                    FROM retrieval_chunks_fts
                    JOIN retrieval_chunks rc ON retrieval_chunks_fts.chunk_id = rc.id
                    WHERE {where}
                    ORDER BY bm25_score
                    LIMIT ?
                    """,
                    params + [limit],
                ).fetchall()
        except sqlite3.OperationalError:
            return None

        results: list[RetrievedSource] = []
        for row in rows:
            results.append(
                RetrievedSource(
                    source_kind=row["source_kind"],
                    source_id=row["source_id"],
                    chunk_index=row["chunk_index"],
                    title=row["title"],
                    text=row["text"],
                    module_id=row["module_id"],
                    assignment_id=row["assignment_id"],
                    updated_at=row["updated_at"],
                    score=float(1.0 / (1.0 + row["bm25_score"])),
                    snippet=_make_snippet(row["text"], question),
                )
            )
        return results

    def query(
        self,
        question: str,
        *,
        source_kind: str | None = None,
        source_id: int | None = None,
        module_id: str | None = None,
        assignment_id: str | None = None,
        limit: int = 5,
    ) -> list[RetrievedSource]:
        if not query_terms(question):
            return []

        # Try FTS5/BM25 first
        fts_results = self._fts_query(
            question,
            source_kind=source_kind,
            source_id=source_id,
            module_id=module_id,
            assignment_id=assignment_id,
            limit=limit,
        )
        if fts_results is not None:
            return fts_results

        # Fall back to lexical scoring
        conditions: list[str] = []
        params: list[object] = []
        if source_kind:
            conditions.append("source_kind = ?")
            params.append(source_kind)
        if source_id is not None:
            conditions.append("source_id = ?")
            params.append(source_id)
        if module_id:
            conditions.append("module_id = ?")
            params.append(module_id)
        if assignment_id:
            conditions.append("assignment_id = ?")
            params.append(assignment_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT source_kind, source_id, chunk_index, title, text,
                       module_id, assignment_id, updated_at
                FROM retrieval_chunks
                {where}
                ORDER BY source_kind, source_id, chunk_index
                """,
                params,
            ).fetchall()

        sources = [self._score_row(row, question) for row in rows]
        sources = [source for source in sources if source.score > 0]
        sources.sort(
            key=lambda source: (
                -source.score,
                source.source_kind,
                source.source_id,
                source.chunk_index,
            )
        )
        return sources[:limit]

    def _score_row(self, row: sqlite3.Row, question: str) -> RetrievedSource:
        score = lexical_score(question, row["title"], row["text"])
        return RetrievedSource(
            source_kind=row["source_kind"],
            source_id=row["source_id"],
            chunk_index=row["chunk_index"],
            title=row["title"],
            text=row["text"],
            module_id=row["module_id"],
            assignment_id=row["assignment_id"],
            updated_at=row["updated_at"],
            score=score,
            snippet=_make_snippet(row["text"], question),
        )

    def _chunk_id(self, chunk: RetrievalChunk) -> str:
        return f"{chunk.source_kind}:{chunk.source_id}:{chunk.chunk_index}"


def _sync_fts(conn: sqlite3.Connection) -> None:
    """Sync FTS5 index from retrieval_chunks. Swallows errors silently."""
    try:
        conn.execute("DELETE FROM retrieval_chunks_fts")
        conn.execute(
            """
            INSERT INTO retrieval_chunks_fts (chunk_id, title, text)
            SELECT id, title, text FROM retrieval_chunks
            """
        )
    except sqlite3.OperationalError:
        pass


def _make_snippet(text: str, question: str, max_len: int = 240) -> str:
    if len(text) <= max_len:
        return text
    terms = query_terms(question)
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return text[:max_len].rstrip() + "..."
    center = min(positions)
    start = max(0, center - 80)
    end = min(len(text), start + max_len)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."
    return snippet
