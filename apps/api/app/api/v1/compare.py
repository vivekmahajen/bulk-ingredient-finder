"""Compare / answer-screen endpoints (PR-7)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.models.enums import PurchaseFrequency
from app.repositories.compare import CompareRepository
from app.schemas.compare import CompareResponse, QuantityCompareRequest
from app.services.compare import compare

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("", response_model=CompareResponse, summary="Compare stores for ingredients")
async def compare_get(
    ingredient_ids: list[uuid.UUID] = Query(min_length=1),
    radius_km: float | None = Query(default=None, ge=0),
    include_delivery: bool = Query(default=True),
    as_of: date | None = Query(default=None),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> CompareResponse:
    repo = CompareRepository(session, ctx.org_id)
    ingredients = await repo.ingredients_by_ids(ingredient_ids)
    if not ingredients:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="No ingredients found",
            detail="None of the requested ingredient_ids exist in this org.",
        )
    return await compare(
        session,
        ctx,
        ingredients=ingredients,
        radius_km=radius_km,
        include_delivery=include_delivery,
        today=as_of,
    )


@router.post(
    "", response_model=CompareResponse, summary="Compare with monthly quantities (savings in $)"
)
async def compare_post(
    payload: QuantityCompareRequest,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> CompareResponse:
    repo = CompareRepository(session, ctx.org_id)
    ingredients = await repo.ingredients_by_ids(payload.ingredient_ids)
    if not ingredients:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="No ingredients found",
            detail="None of the requested ingredient_ids exist in this org.",
        )
    return await compare(
        session,
        ctx,
        ingredients=ingredients,
        radius_km=payload.radius_km,
        include_delivery=payload.include_delivery,
        quantities=payload.quantities,
    )


@router.get(
    "/frequency-run",
    response_model=CompareResponse,
    summary="This week's shopping run: all ingredients at a purchase frequency",
)
async def frequency_run(
    frequency: PurchaseFrequency = Query(),
    radius_km: float | None = Query(default=None, ge=0),
    include_delivery: bool = Query(default=True),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> CompareResponse:
    repo = CompareRepository(session, ctx.org_id)
    ingredients = await repo.ingredients_by_frequency(frequency.value)
    return await compare(
        session,
        ctx,
        ingredients=ingredients,
        radius_km=radius_km,
        include_delivery=include_delivery,
    )
