"""WP3 acceptance tests: Telegram boundary validation for /add_shift."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_context(tmp_db: Path) -> SimpleNamespace:
    settings = Settings(
        _env_file=None,
        telegram_allowed_user_ids=[123],
        data_dir=tmp_db.parent,
    )
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
        bot_data={"settings": settings},
        chat_data={},
    )


@pytest.mark.asyncio
async def test_add_shift_non_numeric_energy_replies_usage(tmp_db: Path) -> None:
    """/add_shift energy=abc must reply with a usage message and not raise."""
    from app.bot import add_shift_command

    update = _make_update(
        123,
        '/add_shift title="Work" start="2026-06-20 14:00" end="2026-06-20 22:00" energy=abc',
    )
    await add_shift_command(update, _make_context(tmp_db))

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "energy" in reply.lower()
    assert "1-5" in reply or "number" in reply.lower()


@pytest.mark.asyncio
async def test_add_shift_valid_energy_persists_shift(tmp_db: Path) -> None:
    """/add_shift with a valid numeric energy must persist the shift."""
    from app.bot import add_shift_command
    from core.academic.service import AcademicService

    update = _make_update(
        123,
        '/add_shift title="Work" start="2026-06-20 14:00" end="2026-06-20 22:00" energy=3',
    )
    await add_shift_command(update, _make_context(tmp_db))

    service = AcademicService(tmp_db)
    shifts = service.list_work_shifts()
    assert any("Work" in s.title for s in shifts)
