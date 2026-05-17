"""Tests for Phase 7 Telegram LLM commands."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import (
    AllowlistFilter,
    explain_note_command,
    flashcards_note_command,
    questions_note_command,
    rewrite_note_command,
    summarize_note_command,
)


@pytest.mark.asyncio
async def test_summarize_note_command() -> None:
    update = _make_update(123, "/summarize_note 1")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service()):
        await _dispatch_if_allowed(update, summarize_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Test note" in reply


@pytest.mark.asyncio
async def test_summarize_note_missing_id() -> None:
    update = _make_update(123, "/summarize_note")
    await _dispatch_if_allowed(update, summarize_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_summarize_note_invalid_id() -> None:
    update = _make_update(123, "/summarize_note abc")
    await _dispatch_if_allowed(update, summarize_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Invalid" in reply


@pytest.mark.asyncio
async def test_explain_note_command() -> None:
    update = _make_update(123, "/explain_note 1")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service()):
        await _dispatch_if_allowed(update, explain_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Test note" in reply


@pytest.mark.asyncio
async def test_questions_note_command() -> None:
    update = _make_update(123, "/questions_note 1")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service()):
        await _dispatch_if_allowed(update, questions_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Test note" in reply


@pytest.mark.asyncio
async def test_flashcards_note_command() -> None:
    update = _make_update(123, "/flashcards_note 1")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service()):
        await _dispatch_if_allowed(update, flashcards_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Test note" in reply


@pytest.mark.asyncio
async def test_rewrite_note_command() -> None:
    update = _make_update(123, "/rewrite_note 1 style=concise")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service()):
        await _dispatch_if_allowed(update, rewrite_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Test note" in reply


@pytest.mark.asyncio
async def test_rewrite_note_default_style() -> None:
    update = _make_update(123, "/rewrite_note 1")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service()):
        await _dispatch_if_allowed(update, rewrite_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Test note" in reply


@pytest.mark.asyncio
async def test_llm_unavailable_message() -> None:
    update = _make_update(123, "/summarize_note 1")
    with patch("app.bot._build_llm_service", return_value=_fake_llm_service_unavailable()):
        await _dispatch_if_allowed(update, summarize_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Ollama" in reply


@pytest.mark.asyncio
async def test_llm_commands_respect_allowlist() -> None:
    update = _make_update(404, "/summarize_note 1")
    if AllowlistFilter(allowed_user_ids=[123]).filter(update):
        await summarize_note_command(update, _make_context())

    update.effective_message.reply_text.assert_not_called()


class _FakeNote:
    def __init__(self) -> None:
        self.id = 1
        self.title = "Test note"
        self.body = "Test body content."


class _FakeLLMResult:
    def __init__(self, success: bool = True, output: str = "Generated output", error: str | None = None, model: str | None = "test-model") -> None:
        self.success = success
        self.output = output
        self.error = error
        self.model = model


class _FakeLLMService:
    def __init__(self, unavailable: bool = False) -> None:
        self._unavailable = unavailable
        self.knowledge = _FakeKnowledgeService()

    def summarize_note(self, note_id: int) -> _FakeLLMResult:
        if self._unavailable:
            return _FakeLLMResult(success=False, error="Connection error: Ollama unavailable")
        return _FakeLLMResult()

    def explain_note(self, note_id: int) -> _FakeLLMResult:
        if self._unavailable:
            return _FakeLLMResult(success=False, error="Connection error")
        return _FakeLLMResult()

    def generate_questions_from_note(self, note_id: int) -> _FakeLLMResult:
        return _FakeLLMResult()

    def generate_flashcards_from_note(self, note_id: int) -> _FakeLLMResult:
        return _FakeLLMResult()

    def rewrite_note(self, note_id: int, style: str = "concise") -> _FakeLLMResult:
        return _FakeLLMResult()


class _FakeKnowledgeService:
    def get_note(self, note_id: int) -> _FakeNote | None:
        if note_id == 1:
            return _FakeNote()
        return None


def _fake_llm_service() -> _FakeLLMService:
    return _FakeLLMService()


def _fake_llm_service_unavailable() -> _FakeLLMService:
    return _FakeLLMService(unavailable=True)


async def _dispatch_if_allowed(update: SimpleNamespace, callback: object) -> None:
    if AllowlistFilter(allowed_user_ids=[update.effective_user.id]).filter(update):
        await callback(update, _make_context())


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_context() -> SimpleNamespace:
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        bot_data=_fake_bot_data(),
    )


def _fake_bot_data() -> dict:
    return {"settings": SimpleNamespace(db_path="/tmp/test.sqlite", timezone="Europe/Dublin")}
