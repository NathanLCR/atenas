"""Telegram service builders."""

from __future__ import annotations

from app.config import Settings
from core.academic.service import AcademicService
from core.knowledge.service import KnowledgeService
from core.llm.engine import OllamaEngine
from core.llm.service import LLMService
from core.nl.agent import AgentLoop
from core.nl.tools import ToolRegistry
from core.nl.traces import AgentTraceStore
from core.notifications.service import NotificationService
from core.retrieval.service import RetrievalService


def build_knowledge_service(settings: Settings) -> KnowledgeService:
    return KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )


def build_retrieval_service(settings: Settings) -> RetrievalService:
    return RetrievalService(
        db_path=settings.db_path,
        timezone=settings.timezone,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout=settings.ollama_timeout_seconds,
        llm_log_path=settings.llm_log_path,
        allowed_file_roots=settings.knowledge_file_roots,
    )


def build_nl_tool_registry(settings: Settings) -> ToolRegistry:
    return ToolRegistry(
        db_path=settings.db_path,
        timezone=settings.timezone,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout=settings.ollama_timeout_seconds,
        web_enabled=getattr(settings, "enable_web_tools", False),
        allowed_file_roots=settings.knowledge_file_roots,
    )


def build_nl_agent(settings: Settings) -> AgentLoop:
    registry = build_nl_tool_registry(settings)
    engine = OllamaEngine(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout_seconds,
    )
    return AgentLoop(
        registry=registry,
        client=engine,
        llm_log_path=settings.llm_log_path,
        trace_store=AgentTraceStore(db_path=settings.db_path),
    )


def build_academic_service(settings: Settings) -> AcademicService:
    return AcademicService(settings.db_path, timezone=settings.timezone)


def build_notification_service(settings: Settings) -> NotificationService:
    return NotificationService(db_path=settings.db_path, timezone=settings.timezone)


def build_llm_service(settings: Settings) -> LLMService:
    return LLMService(
        db_path=settings.db_path,
        timezone=settings.timezone,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout=settings.ollama_timeout_seconds,
        llm_log_path=settings.llm_log_path,
    )
