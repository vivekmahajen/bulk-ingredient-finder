"""API v1 router aggregation.

Feature routers (auth in PR-1, ingredients/stores/prices in PR-2+) are included
here and mounted under ``/api/v1`` by the app factory.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/ping", tags=["meta"], summary="API v1 liveness ping")
async def ping() -> dict[str, str]:
    return {"message": "pong", "version": "v1"}
