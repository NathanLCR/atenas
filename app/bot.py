"""Telegram bot integration for Atenas."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from skills.status import handler as status_handler

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import Application, ContextTypes

logger = logging.getLogger(__name__)


class AllowlistFilter:
    """Allow only configured Telegram user IDs through to handlers."""

    def __init__(self, allowed_user_ids: Sequence[int] | None = None) -> None:
        self._allowed_user_ids = set(allowed_user_ids) if allowed_user_ids is not None else None

    def check_update(self, update: Update) -> bool:
        """Return whether the update should be handled."""

        return self.filter(update)

    def filter(self, update: Update) -> bool:
        """Return whether the update's effective user is allowed."""

        user = update.effective_user
        user_id = user.id if user is not None else None
        allowed_user_ids = self._allowed_user_ids
        if allowed_user_ids is None:
            allowed_user_ids = set(get_settings().TELEGRAM_ALLOWED_USER_IDS)
        if user_id is not None and user_id in allowed_user_ids:
            return True
        logger.warning(f"Blocked Telegram update from user_id={user_id}")
        return False


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /ping."""

    await _reply(update, "pong")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /status with the formatted status skill output."""

    await _reply(update, _get_status_text())


async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /skills with the formatted skill listing."""

    await _reply(update, _get_skills_text())


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to an allowlisted but unknown Telegram command."""

    logger.debug("unknown_telegram_command")
    await _reply(update, "Unknown command. Try /ping, /status, or /skills.")


def build_application(settings: Settings | None = None) -> Application:
    """Build a configured python-telegram-bot application."""

    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    runtime_settings = settings or get_settings()
    token = runtime_settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set; Telegram bot startup is disabled.")

    allowlist_filter = _build_allowlist_filter()
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("ping", ping_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("status", status_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("skills", skills_command, filters=allowlist_filter))
    application.add_handler(MessageHandler(filters.COMMAND & allowlist_filter, unknown_command))
    return application


async def start_bot(app: Application) -> None:
    """Initialize and start the Telegram application under FastAPI control."""

    await app.initialize()
    await app.start()


async def stop_bot(app: Application) -> None:
    """Stop and shut down the Telegram application."""

    if app.running:
        await app.stop()
    await app.shutdown()


def _build_allowlist_filter() -> AllowlistFilter:
    """Build the runtime PTB UpdateFilter subclass for handler registration."""

    from telegram.ext import filters

    class TelegramAllowlistFilter(filters.UpdateFilter, AllowlistFilter):
        def __init__(self) -> None:
            filters.UpdateFilter.__init__(self, name="AllowlistFilter")
            AllowlistFilter.__init__(self)

        def filter(self, update: Update) -> bool:
            return AllowlistFilter.filter(self, update)

    return TelegramAllowlistFilter()


async def _reply(update: Update, text: str) -> None:
    """Reply on the effective message when one exists."""

    message = update.effective_message
    if message is None:
        logger.debug("telegram_update_without_message")
        return
    await message.reply_text(text)


def _get_status_text() -> str:
    """Return formatted status text from the status skill."""

    return status_handler.get_status()


def _get_skills_text() -> str:
    """Return formatted skill text from the status skill."""

    return status_handler.get_skills()
