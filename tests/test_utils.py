"""Tests for shared utility helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.utils import JSONLHandler, ensure_runtime_directories


def test_ensure_runtime_directories_creates_missing_dirs(tmp_path: Path) -> None:
    """A fresh checkout lacks runtime dirs; the helper must create them."""

    inbox = tmp_path / "inbox"
    memory = tmp_path / "nested" / "memory"
    assert not inbox.exists()
    assert not memory.exists()

    ensured = ensure_runtime_directories([inbox, memory])

    assert inbox.is_dir()
    assert memory.is_dir()
    assert set(ensured) == {inbox, memory}


def test_ensure_runtime_directories_is_idempotent(tmp_path: Path) -> None:
    """Re-running against existing directories must not raise."""

    target = tmp_path / "data"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")

    ensure_runtime_directories([target])

    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


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


def test_jsonl_handler_excludes_task_name(tmp_path: Path) -> None:
    """`taskName` (LogRecord attr since 3.12) must not leak into JSONL."""

    log_path = tmp_path / "logs" / "events.jsonl"
    handler = JSONLHandler(log_path)
    record = logging.LogRecord(
        name="tests.task_name",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="evt",
        args=(),
        exc_info=None,
    )
    record.taskName = "Task-1"
    record.event_type = "evt"

    handler.emit(record)
    handler.close()

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert "taskName" not in payload
