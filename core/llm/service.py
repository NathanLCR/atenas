"""Service layer for local LLM assistance over selected notes."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from core.knowledge.service import KnowledgeService
from core.llm.client import OllamaClient
from core.llm.models import LLMActionResult, LLM_ACTIONS, REWRITE_STYLES
from core.llm.prompts import build_prompt
from core.utils import utc_now

logger = logging.getLogger(__name__)


class LLMService:
    """Local LLM assistance over explicitly selected notes.

    All actions operate on a single note identified by ID. No RAG,
    no embeddings, no cloud fallback, no autonomous behaviour.
    """

    def __init__(
        self,
        db_path: Path | str,
        timezone: str | ZoneInfo = "Europe/Dublin",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1:8b",
        ollama_timeout: int = 60,
        llm_log_path: Path | str | None = None,
    ) -> None:
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
        self.knowledge = KnowledgeService(db_path, self.timezone)
        self.client = OllamaClient(
            base_url=ollama_base_url,
            model=ollama_model,
            timeout=ollama_timeout,
        )
        self._ollama_model = ollama_model
        self._llm_log_path = Path(llm_log_path) if llm_log_path is not None else None

    def summarize_note(self, note_id: int) -> LLMActionResult:
        return self._run_action("summarize", note_id)

    def explain_note(self, note_id: int) -> LLMActionResult:
        return self._run_action("explain", note_id)

    def generate_questions_from_note(self, note_id: int) -> LLMActionResult:
        return self._run_action("questions", note_id)

    def generate_flashcards_from_note(self, note_id: int) -> LLMActionResult:
        return self._run_action("flashcards", note_id)

    def rewrite_note(self, note_id: int, style: str = "concise") -> LLMActionResult:
        if style not in REWRITE_STYLES:
            return LLMActionResult(
                success=False, action="rewrite", source_kind="note", source_id=note_id,
                error=f"Invalid style '{style}'. Allowed: {', '.join(sorted(REWRITE_STYLES))}",
            )
        return self._run_action("rewrite", note_id, style=style)

    def _run_action(self, action: str, note_id: int, style: str | None = None) -> LLMActionResult:
        if action not in LLM_ACTIONS:
            return LLMActionResult(
                success=False, action=action, source_kind="note", source_id=note_id,
                error=f"Unknown action: {action}",
            )

        note = self.knowledge.get_note(note_id)
        if note is None:
            return LLMActionResult(
                success=False, action=action, source_kind="note", source_id=note_id,
                error=f"Note #{note_id} not found.",
            )

        if not note.body or not note.body.strip():
            return LLMActionResult(
                success=False, action=action, source_kind="note", source_id=note_id,
                error="Note body is empty.",
            )

        prompt = build_prompt(action, note.body, style)
        started = time.perf_counter()

        try:
            response = self.client.generate(prompt)
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = LLMActionResult(
                success=True,
                action=action,
                source_kind="note",
                source_id=note_id,
                output=response.text,
                model=response.model,
            )
            self._log_call(action, response.model, note_id, True, latency_ms)
            return result
        except (ConnectionError, TimeoutError, OSError) as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._log_call(action, self._ollama_model, note_id, False, latency_ms, str(exc))
            return LLMActionResult(
                success=False, action=action, source_kind="note", source_id=note_id,
                error=str(exc),
            )

    def _log_call(
        self,
        action: str,
        model: str,
        source_id: int,
        success: bool,
        latency_ms: int,
        error: str | None = None,
    ) -> None:
        """Append LLM call metadata using the centralized audit logger."""

        from core.llm.audit import log_llm_call

        log_llm_call(
            self._llm_log_path,
            provider="local",
            model=model,
            task_type=f"note_{action}",
            success=success,
            latency_ms=latency_ms,
            error=error,
        )
