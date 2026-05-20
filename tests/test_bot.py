"""Tests for the Phase 2 Telegram bot integration."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.bot import (
    AllowlistFilter,
    build_application,
    natural_language_handler,
    ping_command,
    skills_command,
    status_command,
    unknown_command,
)

Callback = Callable[[SimpleNamespace, SimpleNamespace], Awaitable[None]]


@pytest.mark.asyncio
async def test_allowlist_blocks_unknown_user(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown Telegram users should be blocked silently."""

    update = _make_update(user_id=404, text="/ping")
    context = _make_context()
    allowlist_filter = AllowlistFilter(allowed_user_ids=[123])

    caplog.set_level(logging.WARNING, logger="app.bot")
    if allowlist_filter.filter(update):
        await ping_command(update, context)

    context.bot.send_message.assert_not_called()
    update.effective_message.reply_text.assert_not_called()
    assert "blocked_telegram_update" in caplog.text


@pytest.mark.asyncio
async def test_allowlist_passes_known_user() -> None:
    """Known Telegram users should reach the selected handler."""

    update = _make_update(user_id=123, text="/ping")
    context = _make_context()
    reached = False

    async def handler(inner_update: SimpleNamespace, inner_context: SimpleNamespace) -> None:
        nonlocal reached
        reached = True

    await _dispatch_if_allowed(update, context, handler)

    assert reached is True


def test_telegram_startup_requires_non_empty_allowlist() -> None:
    """A configured Telegram token without allowed users should fail startup."""

    settings = Settings(
        _env_file=None,
        telegram_bot_token="123:abc",
        telegram_allowed_user_ids=[],
    )

    with pytest.raises(RuntimeError, match="TELEGRAM_ALLOWED_USER_IDS"):
        build_application(settings)


@pytest.mark.asyncio
async def test_ping_handler_replies_pong() -> None:
    """The /ping command should reply with pong."""

    update = _make_update(user_id=123, text="/ping")
    await _dispatch_if_allowed(update, _make_context(), ping_command)

    update.effective_message.reply_text.assert_awaited_once_with("pong")


@pytest.mark.asyncio
async def test_status_handler_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The /status command should reply with a non-empty formatted string."""

    monkeypatch.setattr("skills.status.handler.get_status", lambda: "status ok")
    update = _make_update(user_id=123, text="/status")

    await _dispatch_if_allowed(update, _make_context(), status_command)

    reply_text = update.effective_message.reply_text.await_args.args[0]
    assert isinstance(reply_text, str)
    assert reply_text


@pytest.mark.asyncio
async def test_skills_handler_replies(monkeypatch: pytest.MonkeyPatch) -> None:
    """The /skills command should reply with a non-empty formatted string."""

    monkeypatch.setattr("skills.status.handler.get_skills", lambda: "skills ok")
    update = _make_update(user_id=123, text="/skills")

    await _dispatch_if_allowed(update, _make_context(), skills_command)

    reply_text = update.effective_message.reply_text.await_args.args[0]
    assert isinstance(reply_text, str)
    assert reply_text


@pytest.mark.asyncio
async def test_unknown_command_replies_helpful_message() -> None:
    """Unknown allowlisted commands should get the supported command list."""

    update = _make_update(user_id=123, text="/foo")

    await _dispatch_if_allowed(update, _make_context(), unknown_command)

    update.effective_message.reply_text.assert_awaited_once_with(
        "Unknown command. Try /ping, /status, or /skills."
    )


async def _dispatch_if_allowed(
    update: SimpleNamespace,
    context: SimpleNamespace,
    callback: Callback,
) -> None:
    """Run a callback after applying the same allowlist gate used by handlers."""

    if AllowlistFilter(allowed_user_ids=[update.effective_user.id]).filter(update):
        await callback(update, context)


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    """Create the small Update surface used by bot callbacks."""

    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_context() -> SimpleNamespace:
    """Create the small Context surface used by tests."""

    return SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))


def _make_context_with_settings() -> SimpleNamespace:
    """Create a context with bot settings for natural language handler tests."""

    settings = Settings(_env_file=None)
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
        bot_data={"settings": settings},
        chat_data={},
    )


@pytest.mark.asyncio
async def test_natural_language_handler_greeting_calls_conversational_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Greeting messages should be handled by the conversational service."""

    from core.llm.client import OllamaClient
    from core.nl.classifier import NLClassifier
    from core.llm.conversational import ConversationalService

    update = _make_update(user_id=123, text="hello")
    context = _make_context_with_settings()

    mock_client = MagicMock(spec=OllamaClient)
    mock_classifier = MagicMock(spec=NLClassifier)
    mock_classifier.classify.return_value = SimpleNamespace(
        intent="greeting",
        confidence=0.95,
        is_confident=True,
        is_read=True,
        is_write=False,
    )
    mock_conv_service = MagicMock(spec=ConversationalService)
    mock_conv_service.generate_response.return_value = "Hi! I'm Atenas. How can I help you study today?"

    monkeypatch.setattr("app.bot.OllamaClient", lambda **kwargs: mock_client)
    monkeypatch.setattr("app.bot.NLClassifier", lambda client, timezone: mock_classifier)
    monkeypatch.setattr("app.bot.ConversationalService", lambda client: mock_conv_service)

    await natural_language_handler(update, context)

    mock_conv_service.generate_response.assert_called_once_with("hello")
    update.effective_message.reply_text.assert_awaited_once_with("Hi! I'm Atenas. How can I help you study today?")


@pytest.mark.asyncio
async def test_natural_language_handler_conversational_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Conversational messages should be handled by the conversational service."""

    from core.llm.client import OllamaClient
    from core.nl.classifier import NLClassifier
    from core.llm.conversational import ConversationalService

    update = _make_update(user_id=123, text="how are you?")
    context = _make_context_with_settings()

    mock_client = MagicMock(spec=OllamaClient)
    mock_classifier = MagicMock(spec=NLClassifier)
    mock_classifier.classify.return_value = SimpleNamespace(
        intent="conversational",
        confidence=0.90,
        is_confident=True,
        is_read=True,
        is_write=False,
    )
    mock_conv_service = MagicMock(spec=ConversationalService)
    mock_conv_service.generate_response.return_value = "I'm doing well! Ready to help you study."

    monkeypatch.setattr("app.bot.OllamaClient", lambda **kwargs: mock_client)
    monkeypatch.setattr("app.bot.NLClassifier", lambda client, timezone: mock_classifier)
    monkeypatch.setattr("app.bot.ConversationalService", lambda client: mock_conv_service)

    await natural_language_handler(update, context)

    mock_conv_service.generate_response.assert_called_once_with("how are you?")
    update.effective_message.reply_text.assert_awaited_once_with("I'm doing well! Ready to help you study.")
