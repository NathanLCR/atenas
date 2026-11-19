"""Text extraction for registered files that are not plain text."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PDF_SUFFIX = ".pdf"
MAX_PDF_PAGES = 300
_CACHE_LIMIT = 64
_cache: dict[tuple[str, int, int, int], str | None] = {}


def extract_pdf_text(
    path: Path,
    *,
    max_chars: int,
    max_pages: int = MAX_PDF_PAGES,
) -> str | None:
    """Extract text from a PDF, capped by pages and characters.

    Returns None for encrypted, corrupt, or image-only PDFs. Never raises.
    Results are cached by (path, mtime, size) so repeated incremental syncs do
    not re-parse unchanged files.
    """

    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_mtime_ns, stat.st_size, max_chars)
    if key in _cache:
        return _cache[key]
    text = _extract(path, max_chars=max_chars, max_pages=max_pages)
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = text
    return text


def _extract(path: Path, *, max_chars: int, max_pages: int) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            logger.warning(
                "pdf_extraction_skipped",
                extra={"event_type": "pdf_extraction_skipped", "reason": "encrypted"},
            )
            return None
        parts: list[str] = []
        total = 0
        for index, page in enumerate(reader.pages):
            if index >= max_pages or total >= max_chars:
                break
            page_text = (page.extract_text() or "").strip()
            if page_text:
                parts.append(page_text)
                total += len(page_text) + 2
        text = "\n\n".join(parts)[:max_chars].strip()
        if not text:
            logger.info(
                "pdf_extraction_skipped",
                extra={"event_type": "pdf_extraction_skipped", "reason": "no_text"},
            )
            return None
        return text
    except Exception as exc:  # pypdf raises many error types on corrupt input
        logger.warning(
            "pdf_extraction_failed",
            extra={
                "event_type": "pdf_extraction_failed",
                "error_type": type(exc).__name__,
            },
        )
        return None
