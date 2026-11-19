"""Tests for /start, /help, command menu, typing indicator, and uploads."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot import AllowlistFilter, build_application, natural_language_handler
from app.config import Settings
from app.telegram_onboarding import (
    build_bot_commands,
    format_help_text,
    help_command,
    register_command_menu,
    start_command,
    typing_indicator,
)
from app.telegram_uploads import document_handler, sanitize_filename
from core.command_catalog import COMMAND_GROUPS
from core.db import init_db


def _settings(tmp_path: Path, **kw) -> Settings:
    inbox = tmp_path / "inbox"
    inbox.mkdir(exist_ok=True)
    return Settings(
        _env_file=None,
        telegram_bot_token="123:abc",
        telegram_allowed_user_ids=[123],
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        inbox_dir=inbox,
        knowledge_file_roots=[inbox],
        **kw,
    )


def _update(user_id=123, text="", document=None, caption=None):
    message = SimpleNamespace(
        text=text, reply_text=AsyncMock(), document=document, caption=caption, chat_id=9
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        effective_chat=SimpleNamespace(id=9),
    )


def _doc(name, size):
    return SimpleNamespace(file_name=name, file_size=size, file_id="f1")


def _context(settings, content=b"hello"):
    async def download_to_drive(custom_path):
        Path(custom_path).write_bytes(content)

    tg_file = SimpleNamespace(download_to_drive=download_to_drive)
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=tg_file),
        send_chat_action=AsyncMock(),
        send_message=AsyncMock(),
    )
    return SimpleNamespace(bot=bot, bot_data={"settings": settings}, user_data={})


def _minimal_pdf(text: str) -> bytes:
    """Build a one-page PDF containing `text` using pypdf's writer."""

    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
    })
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _typing_tasks() -> list:
    return [t for t in asyncio.all_tasks() if "_typing_loop" in repr(t) and not t.done()]


@pytest.mark.asyncio
async def test_start_and_help() -> None:
    update = _update()
    await start_command(update, SimpleNamespace())
    welcome = update.effective_message.reply_text.await_args.args[0]
    assert "/help" in welcome and "confirm" in welcome

    update = _update()
    await help_command(update, SimpleNamespace())
    text = update.effective_message.reply_text.await_args.args[0]
    for _, commands in COMMAND_GROUPS:
        for command in commands:
            assert command in text
    assert "/start" in format_help_text()


def test_start_help_handlers_registered(tmp_path: Path) -> None:
    app = build_application(_settings(tmp_path))
    names = {tuple(h.commands) for h in app.handlers[0] if hasattr(h, "commands")}
    assert ("start",) in names and ("help",) in names


def test_menu_commands_cover_catalog() -> None:
    commands = build_bot_commands()
    names = [n for n, _ in commands]
    assert "start" in names and "help" in names
    assert all(d for _, d in commands)


@pytest.mark.asyncio
async def test_menu_registration_failure_tolerated() -> None:
    bad = SimpleNamespace(set_my_commands=AsyncMock(side_effect=RuntimeError("boom")))
    assert await register_command_menu(bad) is False
    ok = SimpleNamespace(set_my_commands=AsyncMock())
    assert await register_command_menu(ok) is True
    ok.set_my_commands.assert_awaited_once()


@pytest.mark.asyncio
async def test_typing_indicator_refreshes_and_cancels() -> None:
    context = SimpleNamespace(bot=SimpleNamespace(send_chat_action=AsyncMock()))
    async with typing_indicator(_update(), context, interval=0.01):
        await asyncio.sleep(0.08)
    calls = context.bot.send_chat_action.await_count
    assert calls >= 2
    await asyncio.sleep(0.05)
    assert context.bot.send_chat_action.await_count == calls
    assert not _typing_tasks()


@pytest.mark.asyncio
async def test_typing_cancelled_when_agent_fails(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    context = _context(settings)

    class Boom:
        assembler = SimpleNamespace()

        def run(self, *args, **kwargs):
            raise RuntimeError("llm down")

    monkeypatch.setattr("app.bot._build_nl_agent", lambda c: Boom())
    with pytest.raises(RuntimeError):
        await natural_language_handler(_update(text="hi"), context)
    context.bot.send_chat_action.assert_awaited()
    assert not _typing_tasks()


def test_non_allowlisted_user_is_dropped_before_handlers() -> None:
    # The NL handler is registered behind the allowlist filter, so unknown users
    # never reach it and no typing action is ever sent for them.
    assert AllowlistFilter(allowed_user_ids=[123]).filter(_update(user_id=404)) is False


def test_sanitize_filename() -> None:
    assert sanitize_filename("../../etc/pass wd.PDF") == ("pass_wd", ".pdf")
    assert sanitize_filename(None) == ("upload", "")
    assert sanitize_filename("..\\..\\.env") == ("env", "")


@pytest.mark.asyncio
async def test_upload_rejects_non_allowlisted(tmp_path) -> None:
    settings = _settings(tmp_path)
    context = _context(settings)
    update = _update(user_id=404, document=_doc("a.pdf", 10))
    await document_handler(update, context)
    context.bot.get_file.assert_not_called()
    update.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_upload_rejects_bad_extension_and_oversize(tmp_path) -> None:
    settings = _settings(tmp_path, telegram_max_upload_mb=1)
    init_db(settings.db_path)
    context = _context(settings)
    for doc in (_doc("evil.exe", 10), _doc("big.pdf", 2 * 1024 * 1024), _doc("x.pdf", None)):
        update = _update(document=doc)
        await document_handler(update, context)
        reply = update.effective_message.reply_text.await_args.args[0]
        assert "Unsupported" in reply or "too large" in reply
    context.bot.get_file.assert_not_called()
    assert list(settings.inbox_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_pdf_registers_and_indexes(tmp_path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    pdf = _minimal_pdf("gradient descent minimises loss")
    context = _context(settings, content=pdf)
    update = _update(document=_doc("../Lecture 1.pdf", len(pdf)), caption="Week 1 slides")
    await document_handler(update, context)
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "File saved" in reply and "Week 1 slides" in reply
    assert "Indexed for search" in reply
    saved = list(settings.inbox_dir.iterdir())
    assert len(saved) == 1 and saved[0].suffix == ".pdf"
    assert saved[0].parent == settings.inbox_dir
    await document_handler(_update(document=_doc("../Lecture 1.pdf", len(pdf))), context)
    assert len(list(settings.inbox_dir.iterdir())) == 2


@pytest.mark.asyncio
async def test_upload_docx_reports_not_searchable(tmp_path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    context = _context(settings, content=b"PK\x03\x04binary")
    update = _update(document=_doc("notes.docx", 12))
    await document_handler(update, context)
    assert "not searchable" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_upload_unknown_module_rejected_and_file_removed(tmp_path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    context = _context(settings)
    update = _update(document=_doc("n.md", 5), caption="module=nope")
    await document_handler(update, context)
    assert "rejected" in update.effective_message.reply_text.await_args.args[0]
    assert list(settings.inbox_dir.iterdir()) == []
