"""Deterministic text chunking for controlled retrieval."""

from __future__ import annotations

import re

DEFAULT_CHUNK_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 150

_WHITESPACE_RE = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    """Normalize text while preserving paragraph boundaries."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split text into stable overlapping chunks.

    Boundaries prefer paragraph, sentence, then word breaks when possible.
    """

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be between 0 and max_chars")

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)
    while start < text_length:
        end = min(start + max_chars, text_length)
        if end < text_length:
            end = _prefer_boundary(normalized, start, end, max_chars)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        next_start = max(start + 1, end - overlap_chars)
        while next_start < text_length and normalized[next_start].isspace():
            next_start += 1
        start = next_start
    return chunks


def _prefer_boundary(text: str, start: int, end: int, max_chars: int) -> int:
    min_boundary = start + max(1, max_chars // 2)
    candidates = [
        text.rfind("\n\n", min_boundary, end),
        text.rfind(". ", min_boundary, end),
        text.rfind("? ", min_boundary, end),
        text.rfind("! ", min_boundary, end),
        text.rfind(" ", min_boundary, end),
    ]
    boundary = max(candidates)
    if boundary <= start:
        return end
    if text[boundary:boundary + 2] == "\n\n":
        return boundary
    return boundary + 1
