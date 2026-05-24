"""Persistent memory management service for Atenas."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from core.db import get_connection
from core.schemas import Importance, MemoryDomain, MemoryItem, StrictModel
from core.time import utc_now_iso
from pydantic import Field

logger = logging.getLogger(__name__)


class MemoryQueryArgs(StrictModel):
    """Arguments for querying memory items."""

    domain: MemoryDomain | None = None
    topic: str | None = None
    tag: str | None = None
    importance: Importance | None = None
    inferred: bool | None = None
    limit: int = Field(default=10, ge=1, le=50)


class MemoryWriteArgs(StrictModel):
    """Arguments for writing a memory item."""

    content: str = Field(min_length=1, max_length=5000)
    summary: str = Field(min_length=1, max_length=2000)
    domain: MemoryDomain
    topic: str = Field(min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: Importance = Importance.MEDIUM
    inferred: bool = True
    sensitive: bool = False


class MemoryUpdateArgs(StrictModel):
    """Arguments for updating an existing memory item."""

    memory_id: str = Field(min_length=1)
    content: str | None = None
    summary: str | None = None
    topic: str | None = None
    tags: list[str] | None = None
    importance: Importance | None = None


class MemoryItemRecord(StrictModel):
    """Memory item returned to callers."""

    id: str
    content: str
    summary: str
    domain: MemoryDomain
    topic: str
    tags: list[str]
    importance: Importance
    source: str
    inferred: bool
    sensitive: bool
    created_at: str
    updated_at: str


class MemoryRepository:
    """SQLite persistence layer for memory_items."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path

    def insert(self, item: MemoryItem) -> MemoryItem:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_items (
                    id, content, summary, domain, topic, tags,
                    importance, source, inferred, sensitive, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.content,
                    item.summary,
                    item.domain.value,
                    item.topic,
                    json.dumps(item.tags, ensure_ascii=False),
                    item.importance.value,
                    item.source,
                    1 if item.inferred else 0,
                    1 if item.sensitive else 0,
                    item.created_at,
                    item.updated_at,
                ),
            )
            conn.commit()
        return item

    def get_by_id(self, memory_id: str) -> MemoryItemRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM memory_items WHERE id = ?", (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    def query(
        self,
        *,
        domain: MemoryDomain | None = None,
        topic: str | None = None,
        tag: str | None = None,
        importance: Importance | None = None,
        inferred: bool | None = None,
        limit: int = 10,
    ) -> list[MemoryItemRecord]:
        conditions: list[str] = []
        params: list[Any] = []

        if domain is not None:
            conditions.append("domain = ?")
            params.append(domain.value)
        if topic is not None:
            conditions.append("topic LIKE ?")
            params.append(f"%{topic}%")
        if tag is not None:
            conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if importance is not None:
            conditions.append("importance = ?")
            params.append(importance.value)
        if inferred is not None:
            conditions.append("inferred = ?")
            params.append(1 if inferred else 0)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM memory_items {where} ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._record_from_row(r) for r in rows]

    def find_similar(
        self,
        *,
        domain: MemoryDomain,
        topic: str,
        limit: int = 5,
    ) -> list[MemoryItemRecord]:
        """Find existing items that may conflict with a new memory entry."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM memory_items
                WHERE domain = ? AND (topic LIKE ? OR content LIKE ?)
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (
                    domain.value,
                    f"%{topic}%",
                    f"%{topic}%",
                    limit,
                ),
            ).fetchall()
        return [self._record_from_row(r) for r in rows]

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        summary: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
        importance: Importance | None = None,
    ) -> MemoryItemRecord | None:
        existing = self.get_by_id(memory_id)
        if existing is None:
            return None

        updates: dict[str, Any] = {}
        if content is not None:
            updates["content"] = content
        if summary is not None:
            updates["summary"] = summary
        if topic is not None:
            updates["topic"] = topic
        if tags is not None:
            updates["tags"] = json.dumps(tags, ensure_ascii=False)
        if importance is not None:
            updates["importance"] = importance.value

        if not updates:
            return existing

        updates["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [memory_id]

        with get_connection(self.db_path) as conn:
            conn.execute(
                f"UPDATE memory_items SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()

        return self.get_by_id(memory_id)

    def delete(self, memory_id: str) -> bool:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM memory_items WHERE id = ?",
                (memory_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM memory_items").fetchone()
        return row["cnt"]

    def _record_from_row(self, row: sqlite3.Row) -> MemoryItemRecord:
        return MemoryItemRecord(
            id=row["id"],
            content=row["content"],
            summary=row["summary"],
            domain=MemoryDomain(row["domain"]),
            topic=row["topic"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            importance=Importance(row["importance"]),
            source=row["source"],
            inferred=bool(row["inferred"]),
            sensitive=bool(row["sensitive"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class MemoryManager:
    """Business logic for persistent memory operations.

    Provides read/write access to the memory_items table with conflict
    detection and resolution.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.repo = MemoryRepository(db_path)

    def read(
        self,
        *,
        domain: MemoryDomain | None = None,
        topic: str | None = None,
        tag: str | None = None,
        importance: Importance | None = None,
        inferred: bool | None = None,
        limit: int = 10,
    ) -> list[MemoryItemRecord]:
        """Query memory items with optional filters."""
        return self.repo.query(
            domain=domain,
            topic=topic,
            tag=tag,
            importance=importance,
            inferred=inferred,
            limit=limit,
        )

    def read_by_id(self, memory_id: str) -> MemoryItemRecord | None:
        """Fetch a single memory item by ID."""
        return self.repo.get_by_id(memory_id)

    def write(
        self,
        *,
        content: str,
        summary: str,
        domain: MemoryDomain,
        topic: str,
        tags: list[str] | None = None,
        importance: Importance = Importance.MEDIUM,
        inferred: bool = True,
        sensitive: bool = False,
        source: str = "telegram",
    ) -> tuple[MemoryItemRecord, list[MemoryItemRecord]]:
        """Write a new memory item.

        Returns (created_item, potential_conflicts).
        Conflicts are detected by matching domain + topic similarity.
        """
        item = MemoryItem(
            content=content,
            summary=summary,
            domain=domain,
            topic=topic,
            tags=tags or [],
            importance=importance,
            source=source,
            inferred=inferred,
            sensitive=sensitive,
        )
        created = self.repo.insert(item)
        conflicts = self.repo.find_similar(domain=domain, topic=topic, limit=3)
        conflicts = [c for c in conflicts if c.id != created.id]
        return created, conflicts

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        summary: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
        importance: Importance | None = None,
    ) -> MemoryItemRecord | None:
        """Update an existing memory item."""
        return self.repo.update(
            memory_id,
            content=content,
            summary=summary,
            topic=topic,
            tags=tags,
            importance=importance,
        )

    def delete(self, memory_id: str) -> bool:
        """Delete a memory item by ID."""
        return self.repo.delete(memory_id)

    def count(self) -> int:
        """Return total memory item count."""
        return self.repo.count()
