"""Store read endpoints (PR-2).

Geocoding, radius search, and writes arrive in PR-5. This exposes the org-scoped
list/detail so seeded stores are reachable now.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.repositories.stores import StoreRepository
from app.schemas.store import StoreRead

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("", response_model=list[StoreRead], summary="List active stores")
async def list_stores(
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[StoreRead]:
    repo = StoreRepository(session, ctx.org_id)
    stores = await repo.list_active()
    return [StoreRead.model_validate(s) for s in stores]


@router.get("/{store_id}", response_model=StoreRead, summary="Get one store")
async def get_store(
    store_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> StoreRead:
    repo = StoreRepository(session, ctx.org_id)
    store = await repo.get(store_id)
    if store is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Store not found",
            detail=f"No store {store_id} in this org.",
        )
    return StoreRead.model_validate(store)
