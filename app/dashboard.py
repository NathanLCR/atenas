"""Read-only Jinja dashboard routes."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import Settings, get_settings
from core.academic.service import AcademicService
from core.db import get_connection
from core.knowledge.service import KnowledgeService
from core.time import utc_now_iso

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
            "utc_now": utc_now_iso(),
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


@router.get("/week", response_class=HTMLResponse)
async def week(request: Request) -> HTMLResponse:
    """Render a read-only weekly schedule and availability page."""

    settings = _get_request_settings(request)
    overview = _get_academic_service(settings).get_week_overview()
    return templates.TemplateResponse(
        request,
        "week.html",
        {
            "overview": overview,
            "format_minutes": _format_minutes,
            "format_time": _format_time,
        },
    )


@router.get("/deadlines", response_class=HTMLResponse)
async def deadlines(request: Request) -> HTMLResponse:
    """Render a read-only open deadlines page."""

    settings = _get_request_settings(request)
    assignments = _get_academic_service(settings).list_upcoming_assignments(limit=50)
    return templates.TemplateResponse(
        request,
        "deadlines.html",
        {
            "assignments": assignments,
        },
    )


@router.get("/plan", response_class=HTMLResponse)
async def plan(request: Request) -> HTMLResponse:
    """Render a read-only deterministic study plan page."""

    settings = _get_request_settings(request)
    study_plan = _get_academic_service(settings).get_study_plan()
    return templates.TemplateResponse(
        request,
        "plan.html",
        {
            "plan": study_plan,
            "format_minutes": _format_minutes,
            "format_time": _format_time,
        },
    )


@router.get("/data", response_class=HTMLResponse)
async def data(request: Request) -> HTMLResponse:
    """Render a read-only data management overview."""

    settings = _get_request_settings(request)
    service = _get_academic_service(settings)
    return templates.TemplateResponse(
        request,
        "data.html",
        {
            "modules": service.list_modules(),
            "class_count": len(service.list_class_sessions()),
            "shift_count": len(service.list_all_work_shifts(limit=100)),
            "assignment_count": len(service.list_all_assignments(include_completed=False)),
        },
    )


@router.get("/notes", response_class=HTMLResponse)
async def notes(request: Request) -> HTMLResponse:
    """Render a read-only notes listing page."""

    settings = _get_request_settings(request)
    service = _get_knowledge_service(settings)
    notes_list = service.list_notes(limit=50)
    return templates.TemplateResponse(
        request,
        "notes.html",
        {"notes": notes_list},
    )


@router.get("/files", response_class=HTMLResponse)
async def files(request: Request) -> HTMLResponse:
    """Render a read-only files listing page."""

    settings = _get_request_settings(request)
    service = _get_knowledge_service(settings)
    files_list = service.list_files(limit=50)
    return templates.TemplateResponse(
        request,
        "files.html",
        {"files": files_list},
    )


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> HTMLResponse:
    """Render a read-only search results page."""

    settings = _get_request_settings(request)
    service = _get_knowledge_service(settings)
    query = request.query_params.get("q", "").strip()
    results = []
    error = None
    if query:
        results, error = service.search(query=query, limit=50)
    return templates.TemplateResponse(
        request,
        "search.html",
        {"query": query, "results": results, "error": error},
    )


@router.get("/llm", response_class=HTMLResponse)
async def llm(request: Request) -> HTMLResponse:
    """Render a read-only LLM call history page."""

    settings = _get_request_settings(request)
    records = _load_llm_call_records(settings)
    return templates.TemplateResponse(
        request,
        "llm.html",
        {"records": records},
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
            FROM llm_calls
            ORDER BY created_at DESC
            LIMIT 50
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table: llm_calls" not in str(exc):
            raise
        logger.debug("llm_calls_table_missing")
        return []
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _get_academic_service(settings: Settings) -> AcademicService:
    """Build the request-scoped academic service."""

    return AcademicService(settings.db_path, timezone=settings.timezone)


def _get_knowledge_service(settings: Settings) -> KnowledgeService:
    """Build the request-scoped knowledge service."""

    return KnowledgeService(settings.db_path, timezone=settings.timezone)


def _format_minutes(minutes: int) -> str:
    """Format minutes as compact hours and minutes."""

    hours, remainder = divmod(minutes, 60)
    return f"{hours}h{remainder:02d}"


def _format_time(value: object) -> str:
    """Format a datetime value as local HH:MM."""

    return value.strftime("%H:%M")
