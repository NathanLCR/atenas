"""Tests for the LLM service layer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.db import init_db
from core.knowledge.models import Note
from core.llm.client import OllamaResponse
from core.llm.service import LLMService


@pytest.fixture
def service(tmp_path: Path) -> LLMService:
    db_path = tmp_path / "test.sqlite"
    init_db(db_path)
    return LLMService(db_path, ollama_base_url="http://localhost:11434", ollama_model="test-model")


def _create_note(service: LLMService, title: str = "Test", body: str = "Test body") -> Note:
    note = Note(title=title, body=body)
    return service.knowledge.repository.create_note(note)


def _mock_ollama_success(text: str = "Generated output") -> MagicMock:
    mock = MagicMock()
    mock.generate.return_value = OllamaResponse(text=text, model="test-model")
    return mock


class TestSummarizeNote:
    def test_summarize_uses_selected_note(self, service: LLMService) -> None:
        note = _create_note(service, body="Backpropagation uses the chain rule.")
        with patch.object(service, "client", _mock_ollama_success("5 bullet summary")):
            result = service.summarize_note(note.id)
        assert result.success is True
        assert result.action == "summarize"
        assert result.source_id == note.id

    def test_missing_note_returns_error(self, service: LLMService) -> None:
        result = service.summarize_note(9999)
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_whitespace_only_body_handled(self, service: LLMService) -> None:
        note = _create_note(service, body="   ")
        result = service.summarize_note(note.id)
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_llm_failure_returns_clean_error(self, service: LLMService) -> None:
        note = _create_note(service)
        mock = MagicMock()
        mock.generate.side_effect = ConnectionError("Ollama unavailable")
        with patch.object(service, "client", mock):
            result = service.summarize_note(note.id)
        assert result.success is False
        assert result.error is not None


class TestExplainNote:
    def test_explain_uses_selected_note(self, service: LLMService) -> None:
        note = _create_note(service, body="Gradient descent optimizes weights.")
        with patch.object(service, "client", _mock_ollama_success("Explanation")):
            result = service.explain_note(note.id)
        assert result.success is True
        assert result.action == "explain"


class TestQuestionsNote:
    def test_questions_uses_selected_note(self, service: LLMService) -> None:
        note = _create_note(service)
        with patch.object(service, "client", _mock_ollama_success("Questions")):
            result = service.generate_questions_from_note(note.id)
        assert result.success is True
        assert result.action == "questions"


class TestFlashcardsNote:
    def test_flashcards_uses_selected_note(self, service: LLMService) -> None:
        note = _create_note(service)
        with patch.object(service, "client", _mock_ollama_success("Flashcards")):
            result = service.generate_flashcards_from_note(note.id)
        assert result.success is True
        assert result.action == "flashcards"


class TestRewriteNote:
    def test_rewrite_with_style(self, service: LLMService) -> None:
        note = _create_note(service)
        with patch.object(service, "client", _mock_ollama_success("Rewritten")):
            result = service.rewrite_note(note.id, style="concise")
        assert result.success is True
        assert result.action == "rewrite"

    def test_rewrite_invalid_style(self, service: LLMService) -> None:
        note = _create_note(service)
        result = service.rewrite_note(note.id, style="invalid")
        assert result.success is False
        assert "Invalid style" in result.error


class TestActionResult:
    def test_result_includes_model(self, service: LLMService) -> None:
        note = _create_note(service)
        with patch.object(service, "client", _mock_ollama_success("Output")):
            result = service.summarize_note(note.id)
        assert result.model == "test-model"

    def test_result_includes_output(self, service: LLMService) -> None:
        note = _create_note(service)
        with patch.object(service, "client", _mock_ollama_success("Custom output")):
            result = service.summarize_note(note.id)
        assert result.output == "Custom output"
