"""Tests for the Phase 8 read-only retrieval dashboard."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from core.retrieval.models import NO_SOURCE_FALLBACK
from core.skill_registry import SkillRegistry


def test_retrieval_route_returns_200(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with TestClient(app) as client:
        response = client.get("/dashboard/retrieval")

    assert response.status_code == 200
    assert "Retrieval" in response.text


def test_retrieval_route_displays_answer_and_sources(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with patch("app.dashboard._get_retrieval_service", return_value=_fake_service()):
        with TestClient(app) as client:
            response = client.get("/dashboard/retrieval?q=attention")

    assert response.status_code == 200
    assert "Grounded answer" in response.text
    assert "N1.1" in response.text


def test_retrieval_route_passes_scope_filters(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())
    service = _fake_service()

    with patch("app.dashboard._get_retrieval_service", return_value=service):
        with TestClient(app) as client:
            response = client.get(
                "/dashboard/retrieval?q=attention&module=mod-1&assignment=asg-1"
            )

    assert response.status_code == 200
    assert service.last_kwargs["module_id"] == "mod-1"
    assert service.last_kwargs["assignment_id"] == "asg-1"


def test_retrieval_route_displays_sources_when_llm_unavailable(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with patch(
        "app.dashboard._get_retrieval_service",
        return_value=_fake_service(error=True),
    ):
        with TestClient(app) as client:
            response = client.get("/dashboard/retrieval?q=attention")

    assert response.status_code == 200
    assert "Local answer unavailable" in response.text
    assert "ollama serve" in response.text
    assert "N1.1" in response.text


def test_retrieval_route_displays_no_source_fallback(settings: Settings) -> None:
    app = create_app(settings=settings, registry=SkillRegistry())

    with patch("app.dashboard._get_retrieval_service", return_value=_fake_service(empty=True)):
        with TestClient(app) as client:
            response = client.get("/dashboard/retrieval?q=unknown")

    assert response.status_code == 200
    assert NO_SOURCE_FALLBACK in response.text


class _FakeSource:
    source_kind = "note"
    source_id = 1
    chunk_index = 0
    title = "Test note"
    snippet = "Attention source snippet."

    @property
    def chunk_label(self) -> str:
        return "N1.1"


class _FakeRetrievalService:
    def __init__(self, empty: bool = False, error: bool = False) -> None:
        self.empty = empty
        self.error = error
        self.last_kwargs: dict[str, object] = {}

    def answer_question(self, question: str, **kwargs: object) -> SimpleNamespace:
        self.last_kwargs = kwargs
        if self.error:
            return SimpleNamespace(
                success=False,
                answer="",
                error="Ollama unavailable",
                sources=[_FakeSource()],
                model=None,
            )
        if self.empty:
            return SimpleNamespace(success=True, answer=NO_SOURCE_FALLBACK, sources=[], model=None)
        return SimpleNamespace(
            success=True,
            answer="Grounded answer [N1.1]",
            sources=[_FakeSource()],
            model="test-model",
        )


def _fake_service(empty: bool = False, error: bool = False) -> _FakeRetrievalService:
    return _FakeRetrievalService(empty=empty, error=error)
