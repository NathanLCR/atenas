"""Tests for shared utility helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.utils import JSONLHandler


def test_jsonl_handler_writes_exception_payload(tmp_path: Path) -> None:
    """JSONL exception logging should not raise a secondary handler error."""

    log_path = tmp_path / "logs" / "errors.jsonl"
    handler = JSONLHandler(log_path)
    logger = logging.getLogger("tests.jsonl_handler")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    try:
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception(
                "test_failure",
                extra={"event_type": "test_failure", "path": tmp_path},
            )

        payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

        assert payload["message"] == "test_failure"
        assert payload["event_type"] == "test_failure"
        assert payload["path"] == str(tmp_path)
        assert "ValueError: boom" in payload["exception"]
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.propagate = True
