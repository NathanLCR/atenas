"""Telegram document upload handling: validate, save to inbox, register, index."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import Settings
from core.academic.validators import parse_kv_args
from core.knowledge.service import KnowledgeService
from core.retrieval.service import RetrievalService, describe_index_result

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

ALLOWED_UPLOAD_SUFFIXES = frozenset({
    ".pdf", ".md", ".txt", ".csv", ".ipynb", ".json", ".xml", ".yaml", ".yml",
    ".docx", ".pptx",
})
_MAX_STEM_CHARS = 80
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str | None) -> tuple[str, str]:
    """Return (safe_stem, lowercase_suffix) from an untrusted filename."""

    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    suffix = Path(base).suffix.lower()
    stem = Path(base).stem if suffix else base
    stem = _SAFE_CHARS.sub("_", stem).strip("._-")[:_MAX_STEM_CHARS]
    return stem or "upload", _SAFE_CHARS.sub("", suffix)


def _authorized(settings: Settings, user_id: int | None) -> bool:
    allowed = settings.TELEGRAM_ALLOWED_USER_IDS
    return bool(allowed) and user_id is not None and user_id in set(allowed)


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a document upload from an allowlisted Telegram user."""

    message = update.effective_message
    if message is None or getattr(message, "document", None) is None:
        return
    user_id = update.effective_user.id if update.effective_user else None
    settings = context.bot_data.get("settings")
    if not isinstance(settings, Settings) or not _authorized(settings, user_id):
        logger.warning(
            "blocked_telegram_update",
            extra={"event_type": "blocked_telegram_update", "user_id": user_id},
        )
        return

    document = message.document
    stem, suffix = sanitize_filename(document.file_name)
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        await message.reply_text(f"Unsupported file type. Allowed: {allowed}")
        return
    max_bytes = settings.telegram_max_upload_mb * 1024 * 1024
    size = document.file_size
    if size is None or size <= 0 or size > max_bytes:
        await message.reply_text(
            f"File is too large or has unknown size (limit {settings.telegram_max_upload_mb} MB)."
        )
        return

    caption = message.caption or ""
    module_id = parse_kv_args(caption).get("module")
    title = parse_kv_args(caption).get("title") or _caption_title(caption) or stem

    inbox = settings.inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
    try:
        tg_file = await context.bot.get_file(document.file_id)
        await tg_file.download_to_drive(custom_path=dest)
        if dest.stat().st_size > max_bytes:
            raise ValueError("downloaded file exceeds size limit")
    except Exception as exc:
        dest.unlink(missing_ok=True)
        logger.warning(
            "telegram_upload_failed",
            extra={
                "event_type": "telegram_upload_failed",
                "actor_user_id": user_id,
                "error_type": type(exc).__name__,
            },
        )
        await message.reply_text("Could not download that file. Please try again.")
        return

    knowledge = KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
    result = knowledge.register_file(path=str(dest), title=title, module_id=module_id)
    if not result.success or result.record_id is None:
        dest.unlink(missing_ok=True)
        await message.reply_text(f"Upload rejected: {result.message}")
        return

    searchable, chunks = _index(settings, result.record_id)
    logger.info(
        "file_uploaded",
        extra={
            "event_type": "file_uploaded",
            "actor_user_id": user_id,
            "file_id": result.record_id,
            "size_bytes": size,
            "file_type": suffix.lstrip("."),
            "searchable": searchable,
        },
    )
    await message.reply_text(
        f"File saved\n\n#{result.record_id} - {title}\n"
        f"{describe_index_result(searchable, chunks, dest.name)}"
    )


def _caption_title(caption: str) -> str:
    """Use the caption minus key=value args as an optional title."""

    cleaned = re.sub(r'\b\w+=(?:"[^"]*"|\S+)', "", caption).strip()
    return cleaned[:200]


def _index(settings: Settings, file_id: int) -> tuple[bool, int]:
    try:
        service = RetrievalService(
            db_path=settings.db_path,
            timezone=settings.timezone,
            ollama_base_url=settings.ollama_base_url,
            ollama_model=settings.ollama_model,
            ollama_timeout=settings.ollama_timeout_seconds,
            llm_log_path=settings.llm_log_path,
            allowed_file_roots=settings.knowledge_file_roots,
        )
        return service.index_file(file_id)
    except Exception as exc:
        logger.warning(
            "upload_index_failed",
            extra={"event_type": "upload_index_failed", "error_type": type(exc).__name__},
        )
        return False, 0
