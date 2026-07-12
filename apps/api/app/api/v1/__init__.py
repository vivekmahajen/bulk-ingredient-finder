"""API v1 router aggregation.

Feature routers (auth in PR-1, ingredients/stores/prices in PR-2+) are included
here and mounted under ``/api/v1`` by the app factory.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    compare,
    ingredients,
    invoices,
    me,
    org,
    prices,
    register,
    search,
    stores,
)

api_router = APIRouter()


@api_router.get("/ping", tags=["meta"], summary="API v1 liveness ping")
async def ping() -> dict[str, str]:
    return {"message": "pong", "version": "v1"}


api_router.include_router(ingredients.router)
api_router.include_router(invoices.router)
api_router.include_router(stores.router)
api_router.include_router(search.router)
api_router.include_router(org.router)
api_router.include_router(prices.router)
api_router.include_router(compare.router)
api_router.include_router(me.router)
api_router.include_router(register.router)
api_router.include_router(auth.router)
