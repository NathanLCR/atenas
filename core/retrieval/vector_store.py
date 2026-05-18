"""SQLite-backed retrieval chunk index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.db import get_connection
from core.retrieval.embeddings import lexical_score, query_terms
from core.retrieval.models import RetrievalChunk, RetrievedSource
from core.time import utc_now_iso

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS retrieval_chunks (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL CHECK(source_kind IN ('note', 'file')),
    source_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    module_id TEXT NULL,
    assignment_id TEXT NULL,
    updated_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    UNIQUE(source_kind, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_source
ON retrieval_chunks(source_kind, source_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_module
ON retrieval_chunks(module_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_assignment
ON retrieval_chunks(assignment_id);
"""


class RetrievalVectorStore:
    """A deterministic SQLite index for note/file text chunks.

    This MVP intentionally uses sparse lexical scoring instead of a vector DB.
    The table shape leaves a clear boundary for a later embedding-backed store.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with get_connection(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

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
            conn.commit()
        return len(chunks)

    def count(self) -> int:
        with get_connection(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) AS count FROM retrieval_chunks").fetchone()["count"])

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
