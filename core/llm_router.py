"""Phase 1 LLM router interface with a mock-only provider."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import Settings, get_settings
from core.schemas import LLMProvider
from core.utils import utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """LLM router response payload."""

    text: str
    parsed: dict[str, Any] | None
    provider: LLMProvider
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMRouter:
    """Mock-only LLM router used in Phase 1."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def call(
        self,
        task_type: str,
        prompt: str,
        schema_model: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Return a deterministic mock LLM response and log the call."""

        started = time.perf_counter()
        parsed = {"mock": True, "task_type": task_type}
        text = json.dumps(parsed)
        response = LLMResponse(
            text=text,
            parsed=parsed,
            provider=LLMProvider.MOCK,
            model="mock",
            input_tokens=len(prompt.split()),
            output_tokens=len(text.split()),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        self._write_call_log(task_type, response, schema_model)
        logger.info(
            "llm_call",
            extra={
                "event_type": "llm_call",
                "provider": response.provider.value,
                "model": response.model,
                "task_type": task_type,
                "latency_ms": response.latency_ms,
            },
        )
        return response

    def _write_call_log(
        self,
        task_type: str,
        response: LLMResponse,
        schema_model: type[BaseModel] | None,
    ) -> None:
        """Append the mock call to logs/llm_calls.jsonl."""

        try:
            path = Path(self.settings.llm_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": utc_now(),
                "event_type": "llm_call",
                "provider": response.provider.value,
                "model": response.model,
                "task_type": task_type,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "schema_model": schema_model.__name__ if schema_model else None,
                "outcome": "success",
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("llm_call_log_write_failed", extra={"event_type": "llm_call_log_write_failed"})

