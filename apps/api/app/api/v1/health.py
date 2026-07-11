"""Liveness and readiness probes.

``/healthz`` is a pure liveness check (process is up). ``/readyz`` additionally
verifies the database is reachable, so orchestrators can gate traffic on it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session

router = APIRouter()
logger = get_logger("health")


@router.get("/healthz", tags=["health"], summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "rasoi-radar-api"}


@router.get("/readyz", tags=["health"], summary="Readiness probe")
async def readyz(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — report any DB failure as not-ready
        logger.warning("readiness_check_failed", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "down"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "database": "up"},
    )
