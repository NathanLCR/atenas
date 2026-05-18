"""FastAPI routes for Phase 1 health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a minimal healthcheck response."""

    return {"status": "ok"}


@router.get("/status")
async def status(request: Request) -> dict[str, str]:
    """Return the status skill response."""

    response = await request.app.state.registry.dispatch("/status", user_id=0)
    return {"response": response}


@router.get("/skills")
async def skills(request: Request) -> dict[str, str]:
    """Return the skills listing response."""

    response = await request.app.state.registry.dispatch("/skills", user_id=0)
    return {"response": response}
