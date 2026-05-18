"""Shared utility helpers for timestamps, logging, and simple text slugs."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""

    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    """Convert free text into a stable lowercase slug."""

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return slug.strip("-") or "item"


class JSONLHandler(logging.Handler):
    """Logging handler that writes one structured JSON object per line."""

    def __init__(self, filepath: Path) -> None:
        super().__init__()
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        """Write a log record to JSONL."""

        try:
            payload: dict[str, Any] = {
                "timestamp": utc_now(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "event_type": getattr(record, "event_type", record.getMessage()),
            }
            for key, value in record.__dict__.items():
                if key.startswith("_") or key in _STANDARD_LOG_RECORD_KEYS:
                    continue
                payload[key] = _json_safe(value)
            if record.exc_info:
                payload["exception"] = _EXCEPTION_FORMATTER.formatException(record.exc_info)
            with self.filepath.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            self.handleError(record)


def setup_logging(logs_dir: Path, level: str = "INFO") -> None:
    """Configure console, event JSONL, and error JSONL logging."""

    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))

    events = JSONLHandler(logs_dir / "events.jsonl")
    events.setLevel(getattr(logging, level.upper(), logging.INFO))

    errors = JSONLHandler(logs_dir / "errors.jsonl")
    errors.setLevel(logging.ERROR)

    root.addHandler(console)
    root.addHandler(events)
    root.addHandler(errors)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "logging_configured",
        extra={"event_type": "logging_configured", "logs_dir": str(logs_dir)},
    )


def _json_safe(value: Any) -> Any:
    """Return a JSON-serializable representation for log extras."""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


_STANDARD_LOG_RECORD_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}

_EXCEPTION_FORMATTER = logging.Formatter()
