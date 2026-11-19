"""Telegram onboarding: /start, /help, command menu, and typing indicator."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from core.command_catalog import COMMAND_DESCRIPTIONS, COMMAND_GROUPS

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

TYPING_REFRESH_SECONDS = 4.0

WELCOME_TEXT = (
    "Welcome to Atenas, your local study assistant.\n"
    "I track your modules, classes, shifts and deadlines, keep notes, "
    "and answer questions from your notes and uploaded files.\n\n"
    "Just send a normal message, for example:\n"
    '- "What is due this week?"\n'
    '- "Add a note: transformers use self-attention"\n'
    '- "Summarize what my lecture slides say about gradient descent"\n\n'
    "You can also send me a PDF, Markdown or text file to add it to your library.\n\n"
    "Key commands:\n"
    "/today - what is on today\n"
    "/deadlines - upcoming deadlines\n"
    "/plan - generate a study plan\n"
    "/ask_notes - ask about your notes and files\n"
    "/help - full command list\n\n"
    "Anything destructive or that changes your data in a risky way asks you "
    "to confirm first (reply yes or no)."
)


def format_help_text() -> str:
    """Return the grouped command list generated from the shared catalog."""

    lines = ["Atenas commands", ""]
    for group, commands in COMMAND_GROUPS:
        lines.append(f"{group}:")
        for command in commands:
            description = COMMAND_DESCRIPTIONS.get(command, "")
            lines.append(f"{command} - {description}" if description else command)
        lines.append("")
    lines.append("Or just send a plain message and I will figure out what you need.")
    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /start with a welcome message."""

    if update.effective_message is not None:
        await update.effective_message.reply_text(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /help with the grouped command list."""

    if update.effective_message is not None:
        await update.effective_message.reply_text(format_help_text())


def build_bot_commands() -> list[tuple[str, str]]:
    """Return (command, description) pairs for Telegram's command menu."""

    commands: list[tuple[str, str]] = []
    for _, group_commands in COMMAND_GROUPS:
        for command in group_commands:
            name = command.lstrip("/")
            description = COMMAND_DESCRIPTIONS.get(command, name)
            commands.append((name, description[:256]))
    return commands[:100]


async def register_command_menu(bot: Any) -> bool:
    """Publish the command menu to Telegram. Best-effort: never raises."""

    try:
        await bot.set_my_commands(build_bot_commands())
    except Exception as exc:
        logger.warning(
            "set_my_commands_failed",
            extra={"event_type": "set_my_commands_failed", "error_type": type(exc).__name__},
        )
        return False
    return True


async def _typing_loop(bot: Any, chat_id: int, interval: float) -> None:
    from telegram.constants import ChatAction

    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("typing_indicator_failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def typing_indicator(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    interval: float = TYPING_REFRESH_SECONDS,
) -> AsyncIterator[None]:
    """Show the Telegram typing action until the block exits.

    Callers must already have passed the allowlist check.
    """

    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        chat_id = getattr(update.effective_message, "chat_id", None)
    if chat_id is None:
        yield
        return
    task = asyncio.create_task(_typing_loop(context.bot, chat_id, interval))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
