"""Tests for controlled retrieval service behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from core.db import init_db
from core.knowledge.models import FileRecord, Note
from core.llm.client import OllamaResponse
from core.retrieval.models import NO_SOURCE_FALLBACK
from core.retrieval.service import RetrievalService


def _service(tmp_path: Path) -> RetrievalService:
    db_path = tmp_path / "atenas.sqlite"
    init_db(db_path)
    return RetrievalService(db_path, ollama_model="test-model")


def _create_note(service: RetrievalService, title: str, body: str, archived: bool = False) -> Note:
    note = service.repository.create_note(Note(title=title, body=body, archived=archived))
    if archived:
        assert note.id is not None
        service.repository.archive_note(note.id)
        archived_note = service.repository.get_note(note.id)
        assert archived_note is not None
        return archived_note
    return note


def test_rebuild_index_indexes_notes_and_registered_text_files(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create_note(service, "Attention", "Attention uses query key value matching.")
    file_path = tmp_path / "reading.txt"
    file_path.write_text("Retrieval augmented generation needs source grounding.", encoding="utf-8")
    service.repository.create_file(
        FileRecord(
            path=str(file_path),
            filename=file_path.name,
            title="RAG reading",
            file_type="text",
            mime_type="text/plain",
        )
    )

    stats = service.rebuild_index()

    assert stats.notes_indexed == 1
    assert stats.files_indexed == 1
    assert stats.chunks_indexed == 2
    assert service.store.count() == 2


def test_retrieve_sources_returns_source_ids(tmp_path: Path) -> None:
    service = _service(tmp_path)
    note = _create_note(service, "Transformers", "Self attention compares queries and keys.")

    sources, error = service.retrieve_sources("self attention")

    assert error is None
    assert sources
    assert sources[0].source_label == f"N{note.id}"
    assert sources[0].chunk_label == f"N{note.id}.1"


def test_retrieve_sources_excludes_archived_notes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create_note(service, "Archived", "Attention should not be retrieved.", archived=True)

    sources, error = service.retrieve_sources("attention")

    assert error is None
    assert sources == []


def test_answer_no_source_fallback_does_not_call_llm(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create_note(service, "Gradient descent", "Optimization updates model weights.")
    mock_client = MagicMock()
    service.client = mock_client

    result = service.answer_question("bayesian posterior")

    assert result.success is True
    assert result.answer == NO_SOURCE_FALLBACK
    assert result.sources == []
    mock_client.generate.assert_not_called()


def test_answer_uses_local_llm_after_sources(tmp_path: Path) -> None:
    service = _service(tmp_path)
    note = _create_note(service, "Attention", "Attention uses queries, keys, and values.")
    mock_client = MagicMock()
    mock_client.generate.return_value = OllamaResponse(
        text=f"Attention uses queries, keys, and values [N{note.id}.1].",
        model="test-model",
    )
    service.client = mock_client

    result = service.answer_question("what does attention use")

    assert result.success is True
    assert result.model == "test-model"
    assert result.sources[0].source_label == f"N{note.id}"
    prompt = mock_client.generate.call_args.args[0]
    assert f"[N{note.id}.1]" in prompt


def test_ask_note_rejects_archived_note(tmp_path: Path) -> None:
    service = _service(tmp_path)
    note = _create_note(service, "Archived", "This should be hidden.", archived=True)

    result = service.answer_question("hidden", note_id=note.id)

    assert result.success is False
    assert "archived" in result.error
