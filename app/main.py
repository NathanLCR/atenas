"""FastAPI application factory and lifespan setup for Atenas Core."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.bot import build_application, start_bot, stop_bot
from app.config import Settings, get_settings
from app.dashboard import router as dashboard_router
from core.db import init_db
from core.skill_registry import SkillRegistry, get_registry
from core.utils import setup_logging
from skills.status.handler import register_status_skill

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, registry: SkillRegistry | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""

    runtime_settings = settings or get_settings()
    runtime_registry = registry or get_registry()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_logging(runtime_settings.logs_dir, runtime_settings.log_level)
        init_db(runtime_settings.db_path)
        register_status_skill(
            runtime_registry, runtime_settings.db_path, runtime_settings.timezone
        )
        app.state.settings = runtime_settings
        app.state.registry = runtime_registry
        bot_app = None
        if runtime_settings.TELEGRAM_BOT_TOKEN:
            try:
                bot_app = build_application(runtime_settings)
                await start_bot(bot_app)
                app.state.bot_app = bot_app
            except Exception:
                logger.exception("telegram_bot_startup_failed")
                if bot_app is not None:
                    await stop_bot(bot_app)
                    bot_app = None
        else:
            logger.warning(
                "telegram_bot_token_not_set",
                extra={"event_type": "telegram_bot_token_not_set"},
            )
        logger.info(
            "application_started",
            extra={"event_type": "application_started", "app_name": runtime_settings.app_name},
        )
        try:
            yield
        finally:
            bot_app = getattr(app.state, "bot_app", None)
            if bot_app is not None:
                await stop_bot(bot_app)
            logger.info("application_shutdown", extra={"event_type": "application_shutdown"})

    app = FastAPI(title=runtime_settings.app_name, lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(dashboard_router)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    return app


_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """Lazily build the ASGI app on first access (PEP 562).

    Keeps ``uvicorn app.main:app`` working while ensuring a bare
    ``import app.main`` does not read real settings or build the app.
    """

    if name == "app":
        global _app
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
