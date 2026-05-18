"""Tests for Phase 9 Telegram notification commands."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot import AllowlistFilter, reminders_command


@pytest.mark.asyncio
async def test_reminders_command_disabled() -> None:
    update = _make_update(123, "/reminders")
    context = _make_context(notifications_enabled=False)
    fake_settings = _make_settings(notifications_enabled=False)
    with patch("app.bot._get_bot_settings", return_value=fake_settings):
        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await reminders_command(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "disabled" in reply.lower()


@pytest.mark.asyncio
async def test_reminders_command_enabled_no_alerts() -> None:
    update = _make_update(123, "/reminders")
    context = _make_context(notifications_enabled=True)
    fake_settings = _make_settings(notifications_enabled=True)
    fake_service = _make_notification_service(deadline_msg="", overdue_msg="")
    with patch("app.bot._get_bot_settings", return_value=fake_settings), \
         patch("app.bot._build_notification_service", return_value=fake_service):
        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await reminders_command(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "enabled" in reply.lower()
    assert "No deadlines" in reply


@pytest.mark.asyncio
async def test_reminders_command_shows_deadline_alerts() -> None:
    update = _make_update(123, "/reminders")
    context = _make_context(notifications_enabled=True)
    fake_settings = _make_settings(notifications_enabled=True)
    fake_service = _make_notification_service(
        deadline_msg="Deadline alert (1 upcoming):\n  Deadline in 24h: Essay (normal)",
        overdue_msg="",
    )
    with patch("app.bot._get_bot_settings", return_value=fake_settings), \
         patch("app.bot._build_notification_service", return_value=fake_service):
        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await reminders_command(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Deadline alert" in reply


@pytest.mark.asyncio
async def test_reminders_command_shows_overdue() -> None:
    update = _make_update(123, "/reminders")
    context = _make_context(notifications_enabled=True)
    fake_settings = _make_settings(notifications_enabled=True)
    fake_service = _make_notification_service(
        deadline_msg="",
        overdue_msg="Overdue assignments (1):\n  OVERDUE by 5h: Lab",
    )
    with patch("app.bot._get_bot_settings", return_value=fake_settings), \
         patch("app.bot._build_notification_service", return_value=fake_service):
        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await reminders_command(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "OVERDUE" in reply


@pytest.mark.asyncio
async def test_reminders_command_respects_allowlist() -> None:
    update = _make_update(999, "/reminders")
    if AllowlistFilter(allowed_user_ids=[123]).filter(update):
        await reminders_command(update, _make_context())
    update.effective_message.reply_text.assert_not_called()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_settings(
    notifications_enabled: bool = True,
    notifications_chat_id: int | None = None,
    deadline_alert_hours: int = 72,
) -> SimpleNamespace:
    return SimpleNamespace(
        db_path="/tmp/test.sqlite",
        timezone="Europe/Dublin",
        NOTIFICATIONS_ENABLED=notifications_enabled,
        NOTIFICATIONS_CHAT_ID=notifications_chat_id,
        DEADLINE_ALERT_HOURS=deadline_alert_hours,
    )


def _make_context(
    notifications_enabled: bool = True,
    notifications_chat_id: int | None = None,
    deadline_alert_hours: int = 72,
) -> SimpleNamespace:
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        bot_data={"settings": _make_settings(notifications_enabled, notifications_chat_id, deadline_alert_hours)},
    )


def _make_notification_service(deadline_msg: str, overdue_msg: str) -> object:
    service = MagicMock()
    service.format_deadline_alerts_message.return_value = deadline_msg
    service.format_overdue_message.return_value = overdue_msg
    return service
