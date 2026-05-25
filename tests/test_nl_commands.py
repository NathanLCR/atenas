"""Tests for the natural language Telegram handler integration."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.bot import (
    AllowlistFilter,
    archive_note_command,
    cancel_pending_command,
    natural_language_handler,
    pending_command,
)
from core.academic.service import AcademicService
from core.knowledge.service import KnowledgeService
from core.llm.client import OllamaClient, OllamaResponse
from core.nl.runtime_state import AgentRuntimeStore

Callback = Callable[[SimpleNamespace, SimpleNamespace], Awaitable[None]]


def _make_update(user_id: int, text: str) -> SimpleNamespace:
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
        message=message,
    )


def _make_context(
    db_path: Path | None = None,
    *,
    allowed_user_ids: list[int] | None = None,
) -> SimpleNamespace:
    if db_path is None:
        settings = MagicMock()
    else:
        settings = Settings(
            _env_file=None,
            data_dir=db_path.parent,
            telegram_allowed_user_ids=allowed_user_ids or [123],
        )
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
        bot_data={"settings": settings},
    )


def _mock_ollama_response(response_text: str):
    return OllamaResponse(text=response_text, model="llama3.1:8b")


def _patch_generate_sequence(monkeypatch: pytest.MonkeyPatch, responses: list[dict]) -> None:
    serialized = [json.dumps(response) for response in responses]

    def mock_generate(self, prompt: str) -> OllamaResponse:
        if serialized:
            return _mock_ollama_response(serialized.pop(0))
        return _mock_ollama_response(json.dumps({"type": "final", "message": "Done."}))

    monkeypatch.setattr(OllamaClient, "generate", mock_generate)


class TestNLHandlerReadIntent:
    @pytest.mark.asyncio
    async def test_handles_today_intent(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="what's my plan today?")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [{"type": "final", "message": "Today\n\nNo classes found."}],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_awaited_once()
        reply = update.effective_message.reply_text.await_args.args[0]
        assert "Today" in reply

    @pytest.mark.asyncio
    async def test_handles_ask_notes_intent(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="what do my notes say about transformers?")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [{"type": "final", "message": "No matching notes yet."}],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        update.effective_message.reply_text.assert_awaited_once()


class TestNLHandlerWriteIntent:
    @pytest.mark.asyncio
    async def test_write_intent_shows_confirmation(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        reply = update.effective_message.reply_text.await_args.args[0]
        assert "Delete duplicate modules?" in reply
        assert "Machine Learning" in reply
        assert context.user_data.get("nl_pending_action") is not None

    @pytest.mark.asyncio
    async def test_write_intent_does_not_mutate_before_confirmation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        assert len(service.list_modules()) == 2

    @pytest.mark.asyncio
    async def test_confirmation_yes_executes_write(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        assert context.user_data.get("nl_pending_action") is not None

        confirm_update = _make_update(user_id=123, text="yes")
        confirm_context = _make_context(tmp_db)
        confirm_context.user_data["nl_pending_action"] = context.user_data["nl_pending_action"]

        if AllowlistFilter(allowed_user_ids=[123]).filter(confirm_update):
            await natural_language_handler(confirm_update, confirm_context)

        reply = confirm_update.effective_message.reply_text.await_args.args[0]
        assert isinstance(reply, str)
        assert confirm_context.user_data.get("nl_pending_action") is None
        assert [module.id for module in service.list_modules()] == [keep.id]

    @pytest.mark.asyncio
    async def test_confirmation_yes_survives_context_restart(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        confirm_update = _make_update(user_id=123, text="yes")
        fresh_context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(confirm_update):
            await natural_language_handler(confirm_update, fresh_context)

        reply = confirm_update.effective_message.reply_text.await_args.args[0]
        assert isinstance(reply, str)
        assert fresh_context.user_data.get("nl_pending_action") is None
        assert [module.id for module in service.list_modules()] == [keep.id]
        assert AgentRuntimeStore(tmp_db).get_active_pending_action(actor_user_id=123) is None

    @pytest.mark.asyncio
    async def test_confirmation_no_survives_context_restart(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        cancel_update = _make_update(user_id=123, text="no")
        fresh_context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(cancel_update):
            await natural_language_handler(cancel_update, fresh_context)

        reply = cancel_update.effective_message.reply_text.await_args.args[0]
        assert "Cancelled" in reply
        assert fresh_context.user_data.get("nl_pending_action") is None
        assert len(service.list_modules()) == 2
        assert (
            AgentRuntimeStore(tmp_db).get_active_pending_action(actor_user_id=123)
            is None
        )

    @pytest.mark.asyncio
    async def test_different_actor_cannot_confirm_durable_pending_action(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        allowed_user_ids = [123, 999]
        context = _make_context(tmp_db, allowed_user_ids=allowed_user_ids)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=allowed_user_ids).filter(update):
            await natural_language_handler(update, context)

        store = AgentRuntimeStore(tmp_db)
        assert store.get_active_pending_action(actor_user_id=123) is not None

        confirm_update = _make_update(user_id=999, text="yes")
        fresh_context = _make_context(tmp_db, allowed_user_ids=allowed_user_ids)

        if AllowlistFilter(allowed_user_ids=allowed_user_ids).filter(confirm_update):
            await natural_language_handler(confirm_update, fresh_context)

        assert len(service.list_modules()) == 2
        assert store.get_active_pending_action(actor_user_id=123) is not None

    @pytest.mark.asyncio
    async def test_confirmation_no_cancels(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        cancel_update = _make_update(user_id=123, text="no")
        cancel_context = _make_context(tmp_db)
        cancel_context.user_data["nl_pending_action"] = context.user_data["nl_pending_action"]

        if AllowlistFilter(allowed_user_ids=[123]).filter(cancel_update):
            await natural_language_handler(cancel_update, cancel_context)

        reply = cancel_update.effective_message.reply_text.await_args.args[0]
        assert "Cancelled" in reply
        assert cancel_context.user_data.get("nl_pending_action") is None
        assert len(service.list_modules()) == 2

    @pytest.mark.asyncio
    async def test_pending_command_reports_no_pending_action(self, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="/pending")
        context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await pending_command(update, context)

        reply = update.effective_message.reply_text.await_args.args[0]
        assert reply == "No pending action."

    @pytest.mark.asyncio
    async def test_pending_command_shows_active_pending_action(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        pending_update = _make_update(user_id=123, text="/pending")
        fresh_context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(pending_update):
            await pending_command(pending_update, fresh_context)

        reply = pending_update.effective_message.reply_text.await_args.args[0]
        assert "Pending action: deduplicate_modules" in reply
        assert "Delete duplicate modules?" in reply
        assert "Machine Learning" in reply
        assert 'Reply "yes" to confirm or "no" to cancel.' in reply

    @pytest.mark.asyncio
    async def test_archive_note_command_creates_durable_pending_action(
        self,
        tmp_db: Path,
    ) -> None:
        result = KnowledgeService(tmp_db).create_note(
            title="CNN notes",
            body="Convolution notes",
        )
        assert result.record_id is not None
        update = _make_update(user_id=123, text=f"/archive_note {result.record_id}")
        context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await archive_note_command(update, context)

        pending_update = _make_update(user_id=123, text="/pending")
        fresh_context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(pending_update):
            await pending_command(pending_update, fresh_context)

        reply = pending_update.effective_message.reply_text.await_args.args[0]
        assert "Pending action: archive_note" in reply
        assert "CNN notes" in reply

    @pytest.mark.asyncio
    async def test_cancel_pending_command_cancels_and_blocks_later_yes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        service = AcademicService(tmp_db)
        keep = service.create_module(name="Machine Learning", code="ML")
        delete = service.create_module(name="Machine Learning", code="ML")
        update = _make_update(user_id=123, text="delete duplicate modules")
        context = _make_context(tmp_db)

        _patch_generate_sequence(
            monkeypatch,
            [
                {"type": "tool_call", "tool_name": "detect_duplicate_modules", "arguments": {}},
                {
                    "type": "tool_call",
                    "tool_name": "deduplicate_modules",
                    "arguments": {
                        "groups": [
                            {
                                "canonical_module_id": keep.id,
                                "duplicate_module_ids": [delete.id],
                            }
                        ]
                    },
                },
                {"type": "final", "message": "No pending action to confirm."},
            ],
        )

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        cancel_update = _make_update(user_id=123, text="/cancel_pending")
        cancel_context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(cancel_update):
            await cancel_pending_command(cancel_update, cancel_context)

        cancel_reply = cancel_update.effective_message.reply_text.await_args.args[0]
        assert cancel_reply == "Cancelled pending action."
        assert (
            AgentRuntimeStore(tmp_db).get_active_pending_action(actor_user_id=123)
            is None
        )

        confirm_update = _make_update(user_id=123, text="yes")
        fresh_context = _make_context(tmp_db)

        if AllowlistFilter(allowed_user_ids=[123]).filter(confirm_update):
            await natural_language_handler(confirm_update, fresh_context)

        assert len(service.list_modules()) == 2

    @pytest.mark.asyncio
    async def test_cancel_pending_command_cancels_older_pending_actions(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        knowledge = KnowledgeService(tmp_db)
        first = knowledge.create_note(title="First note", body="First").record_id
        second = knowledge.create_note(title="Second note", body="Second").record_id
        assert first is not None
        assert second is not None

        first_update = _make_update(user_id=123, text=f"/archive_note {first}")
        first_context = _make_context(tmp_db)
        if AllowlistFilter(allowed_user_ids=[123]).filter(first_update):
            await archive_note_command(first_update, first_context)

        second_update = _make_update(user_id=123, text=f"/archive_note {second}")
        second_context = _make_context(tmp_db)
        if AllowlistFilter(allowed_user_ids=[123]).filter(second_update):
            await archive_note_command(second_update, second_context)

        cancel_update = _make_update(user_id=123, text="/cancel_pending")
        cancel_context = _make_context(tmp_db)
        if AllowlistFilter(allowed_user_ids=[123]).filter(cancel_update):
            await cancel_pending_command(cancel_update, cancel_context)

        assert (
            AgentRuntimeStore(tmp_db).get_active_pending_action(actor_user_id=123)
            is None
        )

        _patch_generate_sequence(
            monkeypatch,
            [{"type": "final", "message": "No pending action to confirm."}],
        )
        confirm_update = _make_update(user_id=123, text="yes")
        fresh_context = _make_context(tmp_db)
        if AllowlistFilter(allowed_user_ids=[123]).filter(confirm_update):
            await natural_language_handler(confirm_update, fresh_context)

        first_note = knowledge.get_note(first)
        second_note = knowledge.get_note(second)
        assert first_note is not None
        assert second_note is not None
        assert first_note.archived is False
        assert second_note.archived is False


class TestNLHandlerFallback:
    @pytest.mark.asyncio
    async def test_invalid_agent_decision_is_safe(self, monkeypatch: pytest.MonkeyPatch, tmp_db: Path) -> None:
        update = _make_update(user_id=123, text="hello")
        context = _make_context(tmp_db)

        def mock_generate(self, prompt: str) -> OllamaResponse:
            return _mock_ollama_response(json.dumps({"intent": "today", "confidence": 0.3, "slots": {}}))

        monkeypatch.setattr(OllamaClient, "generate", mock_generate)

        if AllowlistFilter(allowed_user_ids=[123]).filter(update):
            await natural_language_handler(update, context)

        reply = update.effective_message.reply_text.await_args.args[0]
        assert "valid tool decision" in reply
        assert "nothing else changed" in reply.lower()

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
    async def test_unauthorized_user_does_not_invoke_agent(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_db: Path,
    ) -> None:
        update = _make_update(user_id=404, text="what's my plan today?")
        settings = Settings(
            _env_file=None,
            data_dir=tmp_db.parent,
            telegram_allowed_user_ids=[123],
        )
        context = SimpleNamespace(
            bot=SimpleNamespace(send_message=AsyncMock()),
            user_data={},
            bot_data={"settings": settings},
        )
        generate = MagicMock(side_effect=AssertionError("agent should not run"))
        monkeypatch.setattr(OllamaClient, "generate", generate)

        await natural_language_handler(update, context)

        generate.assert_not_called()
        update.effective_message.reply_text.assert_not_awaited()

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
