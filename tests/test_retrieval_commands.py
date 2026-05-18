"""Tests for Phase 8 Telegram retrieval commands."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import (
    AllowlistFilter,
    ask_note_command,
    ask_notes_command,
    sources_command,
)
from core.retrieval.models import NO_SOURCE_FALLBACK


@pytest.mark.asyncio
async def test_ask_notes_command_formats_answer_and_sources() -> None:
    update = _make_update(123, '/ask_notes q="attention"')
    with patch("app.bot._build_retrieval_service", return_value=_fake_retrieval_service()):
        await _dispatch_if_allowed(update, ask_notes_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Answer for" in reply
    assert "Grounded answer" in reply
    assert "[N1.1]" in reply


@pytest.mark.asyncio
async def test_ask_note_command_accepts_positional_note_id() -> None:
    update = _make_update(123, "/ask_note 1 attention")
    with patch("app.bot._build_retrieval_service", return_value=_fake_retrieval_service()):
        await _dispatch_if_allowed(update, ask_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Grounded answer" in reply


@pytest.mark.asyncio
async def test_ask_note_missing_query_returns_usage() -> None:
    update = _make_update(123, "/ask_note 1")

    await _dispatch_if_allowed(update, ask_note_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Usage:" in reply


@pytest.mark.asyncio
async def test_sources_command_formats_source_list() -> None:
    update = _make_update(123, '/sources q="attention"')
    with patch("app.bot._build_retrieval_service", return_value=_fake_retrieval_service()):
        await _dispatch_if_allowed(update, sources_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Sources for" in reply
    assert "[N1.1]" in reply


@pytest.mark.asyncio
async def test_sources_command_uses_no_source_fallback() -> None:
    update = _make_update(123, '/sources q="unknown"')
    with patch("app.bot._build_retrieval_service", return_value=_fake_retrieval_service(empty=True)):
        await _dispatch_if_allowed(update, sources_command)

    reply = update.effective_message.reply_text.await_args.args[0]
    assert reply == NO_SOURCE_FALLBACK


@pytest.mark.asyncio
async def test_retrieval_commands_respect_allowlist() -> None:
    update = _make_update(404, '/ask_notes q="attention"')
    if AllowlistFilter(allowed_user_ids=[123]).filter(update):
        await ask_notes_command(update, _make_context())

    update.effective_message.reply_text.assert_not_called()


class _FakeSource:
    source_kind = "note"
    source_id = 1
    chunk_index = 0
    title = "Test note"
    snippet = "Attention source snippet."
    score = 10.0

    @property
    def source_label(self) -> str:
        return "N1"

    @property
    def chunk_label(self) -> str:
        return "N1.1"


class _FakeRetrievalService:
    def __init__(self, empty: bool = False) -> None:
        self.empty = empty

    def answer_question(self, question: str, **kwargs: object) -> SimpleNamespace:
        if self.empty:
            return SimpleNamespace(success=True, question=question, answer=NO_SOURCE_FALLBACK, sources=[], model=None)
        return SimpleNamespace(
            success=True,
            question=question,
            answer="Grounded answer [N1.1]",
            sources=[_FakeSource()],
            model="test-model",
        )

    def retrieve_sources(self, question: str, **kwargs: object) -> tuple[list[_FakeSource], None]:
        if self.empty:
            return [], None
        return [_FakeSource()], None


def _fake_retrieval_service(empty: bool = False) -> _FakeRetrievalService:
    return _FakeRetrievalService(empty=empty)


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
