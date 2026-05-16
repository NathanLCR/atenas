"""Read-only Jinja dashboard routes."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import Settings, get_settings
from core.db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the dashboard home page."""

    settings = _get_request_settings(request)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "utc_now": datetime.utcnow().isoformat(),
        },
    )


@router.get("/logs", response_class=HTMLResponse)
async def logs(request: Request) -> HTMLResponse:
    """Render the latest read-only LLM call records."""

    settings = _get_request_settings(request)
    records = _load_llm_call_records(settings)
    return templates.TemplateResponse(
        request,
        "logs.html",
        {
            "records": records,
        },
    )


def _get_request_settings(request: Request) -> Settings:
    """Return app-scoped settings when available."""

    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()


def _load_llm_call_records(settings: Settings) -> list[dict[str, object]]:
    """Load the newest dashboard LLM call records from SQLite."""

    connection = get_connection(settings.db_path)
    try:
        rows = connection.execute(
            """
            SELECT *
            FROM llm_call_records
            ORDER BY called_at DESC
            LIMIT 50
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table: llm_call_records" not in str(exc):
            raise
        logger.debug("llm_call_records_table_missing")
        return []
    finally:
        connection.close()
    return [dict(row) for row in rows]
