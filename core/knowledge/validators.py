"""Validation utilities for the knowledge layer."""

from __future__ import annotations

from core.knowledge.models import ALLOWED_SOURCE_TYPES


def validate_note_title(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return ""
    if len(trimmed) > 200:
        return None
    return trimmed


def validate_note_body(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return ""
    if len(trimmed) > 20000:
        return None
    return trimmed


def validate_source_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized if normalized in ALLOWED_SOURCE_TYPES else None


def normalize_tags(tags: list[str] | str | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    result = []
    for tag in tags:
        normalized = tag.strip().lower().replace(" ", "-")
        if normalized and len(normalized) <= 50:
            result.append(normalized)
    return result[:20]


def serialize_tags(tags: list[str]) -> str | None:
    if not tags:
        return None
    return ",".join(tags)


def deserialize_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def derive_file_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    mapping = {
        "pdf": "pdf", "md": "markdown", "txt": "text",
        "docx": "document", "doc": "document",
        "pptx": "slides", "ppt": "slides",
        "xlsx": "spreadsheet", "xls": "spreadsheet",
        "ipynb": "notebook", "csv": "spreadsheet",
        "py": "code", "js": "code", "ts": "code",
        "html": "code", "css": "code",
        "json": "data", "yaml": "data", "yml": "data", "xml": "data",
    }
    return mapping.get(ext, "other")


def derive_mime_type(path: str) -> str | None:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    mapping = {
        "pdf": "application/pdf", "md": "text/markdown", "txt": "text/plain",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ipynb": "application/x-ipynb+json", "csv": "text/csv",
        "json": "application/json", "html": "text/html",
        "py": "text/x-python", "js": "text/javascript",
    }
    return mapping.get(ext)
