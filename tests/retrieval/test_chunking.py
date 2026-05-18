"""Tests for deterministic retrieval chunking."""

from __future__ import annotations

import pytest

from core.retrieval.chunking import chunk_text, normalize_text


def test_normalize_text_preserves_paragraphs() -> None:
    text = "  First   paragraph. \r\n\r\n\r\n Second\tparagraph.  "

    assert normalize_text(text) == "First paragraph.\n\nSecond paragraph."


def test_chunk_text_splits_long_text_with_limits() -> None:
    text = " ".join(f"token{i}" for i in range(80))

    chunks = chunk_text(text, max_chars=120, overlap_chars=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert chunks[0] != chunks[1]


def test_chunk_text_returns_empty_for_whitespace() -> None:
    assert chunk_text(" \n \t ") == []


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text("hello", max_chars=10, overlap_chars=10)
