"""Tests for core.memory_manager."""

from pathlib import Path

import pytest

from core.db import init_db
from core.memory_manager import MemoryManager, MemoryItemRecord
from core.schemas import Importance, MemoryDomain


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_memory.sqlite"
    init_db(path)
    return path


@pytest.fixture
def manager(db_path: Path) -> MemoryManager:
    return MemoryManager(db_path)


class TestMemoryWrite:
    def test_write_creates_item(self, manager: MemoryManager) -> None:
        created, conflicts = manager.write(
            content="User prefers study sessions in the morning",
            summary="Prefers morning study sessions",
            domain=MemoryDomain.PREFERENCES,
            topic="study_schedule",
        )
        assert created.id is not None
        assert created.summary == "Prefers morning study sessions"
        assert created.domain == MemoryDomain.PREFERENCES
        assert created.inferred is True
        assert created.sensitive is False
        assert conflicts == []

    def test_write_with_tags(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="Working on NLP thesis",
            summary="NLP thesis topic",
            domain=MemoryDomain.STUDIES,
            topic="nlp",
            tags=["thesis", "nlp", "research"],
        )
        assert created.tags == ["thesis", "nlp", "research"]

    def test_write_detects_conflicts(self, manager: MemoryManager) -> None:
        manager.write(
            content="User studies computer science",
            summary="CS student",
            domain=MemoryDomain.STUDIES,
            topic="computer_science",
        )
        created, conflicts = manager.write(
            content="User is enrolled in CS program",
            summary="CS enrollment",
            domain=MemoryDomain.STUDIES,
            topic="computer_science",
        )
        assert len(conflicts) >= 1
        assert created.id not in [c.id for c in conflicts]

    def test_write_stated_fact(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="User has exam on May 21",
            summary="Exam on May 21",
            domain=MemoryDomain.ASSIGNMENTS,
            topic="exam",
            inferred=False,
        )
        assert created.inferred is False

    def test_write_sensitive(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="User has health condition affecting study",
            summary="Health consideration",
            domain=MemoryDomain.PREFERENCES,
            topic="health",
            sensitive=True,
        )
        assert created.sensitive is True


class TestMemoryRead:
    def test_read_all(self, manager: MemoryManager) -> None:
        manager.write(
            content="Item 1",
            summary="Summary 1",
            domain=MemoryDomain.STUDIES,
            topic="topic_a",
        )
        manager.write(
            content="Item 2",
            summary="Summary 2",
            domain=MemoryDomain.WORK,
            topic="topic_b",
        )
        items = manager.read()
        assert len(items) == 2

    def test_read_by_domain(self, manager: MemoryManager) -> None:
        manager.write(
            content="Study item",
            summary="Study summary",
            domain=MemoryDomain.STUDIES,
            topic="study",
        )
        manager.write(
            content="Work item",
            summary="Work summary",
            domain=MemoryDomain.WORK,
            topic="work",
        )
        items = manager.read(domain=MemoryDomain.STUDIES)
        assert len(items) == 1
        assert items[0].domain == MemoryDomain.STUDIES

    def test_read_by_topic(self, manager: MemoryManager) -> None:
        manager.write(
            content="NLP notes",
            summary="NLP topic",
            domain=MemoryDomain.STUDIES,
            topic="nlp",
        )
        manager.write(
            content="ML notes",
            summary="ML topic",
            domain=MemoryDomain.STUDIES,
            topic="ml",
        )
        items = manager.read(topic="nlp")
        assert len(items) == 1
        assert "nlp" in items[0].topic.lower()

    def test_read_by_tag(self, manager: MemoryManager) -> None:
        manager.write(
            content="Tagged item",
            summary="Tagged summary",
            domain=MemoryDomain.STUDIES,
            topic="tagged",
            tags=["important", "review"],
        )
        manager.write(
            content="Untagged item",
            summary="Untagged summary",
            domain=MemoryDomain.STUDIES,
            topic="untagged",
        )
        items = manager.read(tag="important")
        assert len(items) == 1

    def test_read_by_importance(self, manager: MemoryManager) -> None:
        manager.write(
            content="Critical item",
            summary="Critical summary",
            domain=MemoryDomain.STUDIES,
            topic="critical",
            importance=Importance.CRITICAL,
        )
        manager.write(
            content="Low item",
            summary="Low summary",
            domain=MemoryDomain.STUDIES,
            topic="low",
            importance=Importance.LOW,
        )
        items = manager.read(importance=Importance.CRITICAL)
        assert len(items) == 1
        assert items[0].importance == Importance.CRITICAL

    def test_read_by_inferred(self, manager: MemoryManager) -> None:
        manager.write(
            content="Inferred fact",
            summary="Inferred summary",
            domain=MemoryDomain.STUDIES,
            topic="inferred",
            inferred=True,
        )
        manager.write(
            content="Stated fact",
            summary="Stated summary",
            domain=MemoryDomain.STUDIES,
            topic="stated",
            inferred=False,
        )
        items = manager.read(inferred=False)
        assert len(items) == 1
        assert items[0].inferred is False

    def test_read_limit(self, manager: MemoryManager) -> None:
        for i in range(5):
            manager.write(
                content=f"Item {i}",
                summary=f"Summary {i}",
                domain=MemoryDomain.STUDIES,
                topic=f"topic_{i}",
            )
        items = manager.read(limit=2)
        assert len(items) == 2

    def test_read_by_id(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="Specific item",
            summary="Specific summary",
            domain=MemoryDomain.STUDIES,
            topic="specific",
        )
        item = manager.read_by_id(created.id)
        assert item is not None
        assert item.id == created.id
        assert item.summary == "Specific summary"

    def test_read_by_id_not_found(self, manager: MemoryManager) -> None:
        item = manager.read_by_id("nonexistent-id")
        assert item is None


class TestMemoryUpdate:
    def test_update_summary(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="Original content",
            summary="Original summary",
            domain=MemoryDomain.STUDIES,
            topic="update_test",
        )
        updated = manager.update(created.id, summary="New summary")
        assert updated is not None
        assert updated.summary == "New summary"
        assert updated.content == "Original content"

    def test_update_content(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="Original content",
            summary="Original summary",
            domain=MemoryDomain.STUDIES,
            topic="update_test",
        )
        updated = manager.update(created.id, content="New content")
        assert updated is not None
        assert updated.content == "New content"

    def test_update_not_found(self, manager: MemoryManager) -> None:
        updated = manager.update("nonexistent-id", summary="New summary")
        assert updated is None

    def test_update_no_changes(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="Content",
            summary="Summary",
            domain=MemoryDomain.STUDIES,
            topic="update_test",
        )
        updated = manager.update(created.id)
        assert updated is not None
        assert updated.summary == "Summary"


class TestMemoryDelete:
    def test_delete(self, manager: MemoryManager) -> None:
        created, _ = manager.write(
            content="To delete",
            summary="Delete summary",
            domain=MemoryDomain.STUDIES,
            topic="delete_test",
        )
        result = manager.delete(created.id)
        assert result is True
        assert manager.read_by_id(created.id) is None

    def test_delete_not_found(self, manager: MemoryManager) -> None:
        result = manager.delete("nonexistent-id")
        assert result is False


class TestMemoryCount:
    def test_count_empty(self, manager: MemoryManager) -> None:
        assert manager.count() == 0

    def test_count_after_writes(self, manager: MemoryManager) -> None:
        for i in range(3):
            manager.write(
                content=f"Item {i}",
                summary=f"Summary {i}",
                domain=MemoryDomain.STUDIES,
                topic=f"topic_{i}",
            )
        assert manager.count() == 3
