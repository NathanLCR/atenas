"""Tests for the natural language Telegram handler integration."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.bot import AllowlistFilter, natural_language_handler
from core.academic.service import AcademicService
from core.llm.client import OllamaClient, OllamaResponse
from core.retrieval.service import RetrievalService

Callback = Callable[[SimpleNamespace, SimpleNamespace], Awaitable[None]]


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_context(db_path: Path | None = None) -> SimpleNamespace:
    if db_path is None:
        settings = MagicMock()
    else:
        settings = Settings(_env_file=None, data_dir=db_path.parent)
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
        bot_data={"settings": settings},
    )


def _mock_ollama_response(response_text: str):
    return OllamaResponse(text=response_text, model="llama3.1:8b")


class TestNLHandlerReadIntent:
    @pytest.mark.asyncio
    async def test_handles_today_intent(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="what's my plan today?")
        context = _make_context(tmp_db)

        response = json.dumps({"intent": "today", "confidence": 0.95, "slots": {}})

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_awaited_once()
        reply = update.effective_message.reply_text.await_args.args[0]
        assert "Today" in reply

    @pytest.mark.asyncio
    async def test_handles_ask_notes_intent(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="what do my notes say about transformers?")
        context = _make_context(tmp_db)

        response = json.dumps({"intent": "ask_notes", "confidence": 0.9, "slots": {"query": "transformers"}})

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)
        monkeypatch.setattr(
            RetrievalService,
            "answer_question",
            lambda self, query, max_sources=5: SimpleNamespace(
                success=True,
                question=query,
                answer="No matching notes yet.",
                sources=[],
                model=None,
                error=None,
            ),
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_awaited_once()


class TestNLHandlerWriteIntent:
    @pytest.mark.asyncio
    async def test_write_intent_shows_confirmation(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="add assignment ML exam due Friday")
        context = _make_context(tmp_db)

        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.92,
            "slots": {"title": "ML exam", "due_at": "Friday", "priority": "high"},
        })

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        reply = update.effective_message.reply_text.await_args.args[0]
        assert "Add assignment?" in reply
        assert "ML exam" in reply
        assert context.user_data.get("nl_pending_confirmation") is not None

    @pytest.mark.asyncio
    async def test_write_intent_does_not_mutate_before_confirmation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        update = _make_update(user_id=123, text="add assignment Test due 2026-06-01")
        context = _make_context(tmp_db)

        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.92,
            "slots": {"title": "Test", "due_at": "2026-06-01 23:59", "priority": "3"},
        })

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        assignments = AcademicService(tmp_db).list_all_assignments(include_completed=True)
        assert assignments == []

    @pytest.mark.asyncio
    async def test_confirmation_yes_executes_write(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="add assignment Test due 2026-06-01")
        context = _make_context(tmp_db)

        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.92,
            "slots": {"title": "Test", "due_at": "2026-06-01 23:59", "priority": "3"},
        })

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        assert context.user_data.get("nl_pending_confirmation") is not None

        confirm_update = _make_update(user_id=123, text="yes")
        confirm_context = _make_context(tmp_db)
        confirm_context.user_data["nl_pending_confirmation"] = context.user_data["nl_pending_confirmation"]

        if AllowlistFilter(allowed_user_ids=[123]).filter(confirm_update):
            await natural_language_handler(confirm_update, confirm_context)

        reply = confirm_update.effective_message.reply_text.await_args.args[0]
        assert isinstance(reply, str)
        assert confirm_context.user_data.get("nl_pending_confirmation") is None
        assignments = AcademicService(tmp_db).list_all_assignments(include_completed=True)
        assert len(assignments) == 1

    @pytest.mark.asyncio
    async def test_confirmation_no_cancels(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="add assignment Test due 2026-06-01")
        context = _make_context(tmp_db)

        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.92,
            "slots": {"title": "Test", "due_at": "2026-06-01 23:59", "priority": "3"},
        })

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        cancel_update = _make_update(user_id=123, text="no")
        cancel_context = _make_context(tmp_db)
        cancel_context.user_data["nl_pending_confirmation"] = context.user_data["nl_pending_confirmation"]

        if AllowlistFilter(allowed_user_ids=[123]).filter(cancel_update):
            await natural_language_handler(cancel_update, cancel_context)

        reply = cancel_update.effective_message.reply_text.await_args.args[0]
        assert "Cancelled" in reply
        assert cancel_context.user_data.get("nl_pending_confirmation") is None


class TestNLHandlerFallback:
    @pytest.mark.asyncio
    async def test_low_confidence_shows_suggestion(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="hello")
        context = _make_context(tmp_db)

        response = json.dumps({"intent": "today", "confidence": 0.3, "slots": {}})

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(response)

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        reply = update.effective_message.reply_text.await_args.args[0]
        assert "/ask_notes" in reply

    @pytest.mark.asyncio
    async def test_ollama_unavailable_degrades_gracefully(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="what's my schedule?")
        context = _make_context(tmp_db)

        def mock_generate(self, prompt: str) -> OllamaResponse:
            raise ConnectionError("Ollama unavailable")

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_awaited_once()
        reply = update.effective_message.reply_text.await_args.args[0]
        assert isinstance(reply, str)


class TestNLHandlerEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_message_ignored(self) -> None:
        update = _make_update(user_id=123, text="")
        context = _make_context()

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_whitespace_only_message_ignored(self) -> None:
        update = _make_update(user_id=123, text="   ")
        context = _make_context()

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_not_awaited()
