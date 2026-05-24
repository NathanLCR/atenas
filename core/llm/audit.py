"""Metadata-only LLM call audit logging."""

from __future__ import annotations

import json
from pathlib import Path

from core.utils import utc_now


def log_llm_call(
    path: Path | str | None,
    *,
    provider: str,
    model: str,
    task_type: str,
    success: bool,
    latency_ms: int | None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> None:
    if path is None:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": utc_now(),
        "event_type": "llm_call",
        "provider": provider,
        "model": model,
        "task_type": task_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "success": success,
        "latency_ms": latency_ms,
        "outcome": "success" if success else "error",
        "error": error,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
