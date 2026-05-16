"""FastAPI routes for Phase 1 health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

router = APIRouter()

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _require_api_key(
    api_key: str | None = Depends(API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate the API key from the request header."""

    expected = getattr(settings, "api_key", None)
    if not expected:
        return
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a minimal healthcheck response."""

    return {"status": "ok"}


@router.get("/status", dependencies=[Depends(_require_api_key)])
async def status(request: Request) -> dict[str, str]:
    """Return the status skill response."""

    response = await request.app.state.registry.dispatch("/status", user_id=0)
    return {"response": response}


@router.get("/skills", dependencies=[Depends(_require_api_key)])
async def skills(request: Request) -> dict[str, str]:
    """Return the skills listing response."""

    response = await request.app.state.registry.dispatch("/skills", user_id=0)
    return {"response": response}

