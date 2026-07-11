"""Price-entry endpoints (PR-6): single + bulk capture, list, history."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.models.enums import Category
from app.models.price import PriceEntry
from app.repositories.ingredients import IngredientRepository
from app.repositories.prices import PriceRepository
from app.repositories.stores import StoreRepository
from app.schemas.price import (
    STALE_AFTER_DAYS,
    BulkPriceCreate,
    BulkResult,
    BulkRowResult,
    PaginatedPrices,
    PriceCreate,
    PriceHistory,
    PriceHistoryPoint,
    PriceRead,
    StoreSeries,
)
from app.services import audit
from app.services import prices as price_service

router = APIRouter(tags=["prices"])


def _build_entry(payload: PriceCreate, org_id: uuid.UUID, user_id: uuid.UUID | None) -> PriceEntry:
    return PriceEntry(
        org_id=org_id,
        ingredient_id=payload.ingredient_id,
        store_id=payload.store_id,
        brand=payload.brand,
        pack_desc=payload.pack_desc,
        pack_qty=payload.pack_qty,
        pack_unit=payload.pack_unit,
        price_cents=payload.price_cents,
        currency=payload.currency,
        observed_at=payload.observed_at or date.today(),
        source=payload.source,
        photo_url=payload.photo_url,
        entered_by=user_id,
    )


@router.post(
    "/prices", response_model=PriceRead, status_code=status.HTTP_201_CREATED, summary="Log a price"
)
async def create_price(
    payload: PriceCreate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> PriceRead:
    ingredients = IngredientRepository(session, ctx.org_id)
    stores = StoreRepository(session, ctx.org_id)

    ingredient = await ingredients.get(payload.ingredient_id)
    if ingredient is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Ingredient not found",
            detail=str(payload.ingredient_id),
        )
    if await stores.get(payload.store_id) is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Store not found",
            detail=str(payload.store_id),
        )

    warnings = price_service.unit_category_warnings(ingredient.category, payload.pack_unit)
    entry = _build_entry(payload, ctx.org_id, ctx.user_id)
    session.add(entry)
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="price.create",
        entity="price_entry",
        entity_id=None,
        meta={"ingredient_id": str(payload.ingredient_id), "price_cents": payload.price_cents},
    )
    await session.commit()
    await session.refresh(entry)
    return price_service.to_read(entry, today=date.today(), warnings=warnings)


@router.post(
    "/prices/bulk",
    response_model=BulkResult,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Bulk-log prices (≤200, per-row results)",
)
async def create_prices_bulk(
    payload: BulkPriceCreate,
    response: Response,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> BulkResult:
    ingredients = IngredientRepository(session, ctx.org_id)
    stores = StoreRepository(session, ctx.org_id)

    categories: dict[uuid.UUID, str] = await ingredients.map_categories(
        [e.ingredient_id for e in payload.entries]
    )
    valid_stores = await stores.existing_ids([e.store_id for e in payload.entries])

    results: list[BulkRowResult] = []
    created = 0

    for i, item in enumerate(payload.entries):
        if item.ingredient_id not in categories:
            results.append(BulkRowResult(index=i, ok=False, error="Unknown ingredient_id"))
            continue
        if item.store_id not in valid_stores:
            results.append(BulkRowResult(index=i, ok=False, error="Unknown store_id"))
            continue
        warnings = price_service.unit_category_warnings(
            Category(categories[item.ingredient_id]), item.pack_unit
        )
        try:
            async with session.begin_nested():
                entry = _build_entry(item, ctx.org_id, ctx.user_id)
                session.add(entry)
                await session.flush()
            results.append(BulkRowResult(index=i, ok=True, id=entry.id, warnings=warnings))
            created += 1
        except Exception as exc:  # noqa: BLE001 — isolate one bad row from the batch
            results.append(BulkRowResult(index=i, ok=False, error=str(exc)))

    await session.commit()
    if created == len(payload.entries):
        response.status_code = status.HTTP_201_CREATED
    return BulkResult(created=created, failed=len(payload.entries) - created, results=results)


@router.get("/prices", response_model=PaginatedPrices, summary="List prices (paginated)")
async def list_prices(
    ingredient_id: uuid.UUID | None = Query(default=None),
    store_id: uuid.UUID | None = Query(default=None),
    since: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> PaginatedPrices:
    repo = PriceRepository(session, ctx.org_id)
    rows, total = await repo.list_prices(
        ingredient_id=ingredient_id, store_id=store_id, since=since, limit=limit, offset=offset
    )
    today = date.today()
    return PaginatedPrices(
        items=[price_service.to_read(r, today=today) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/ingredients/{ingredient_id}/price-history",
    response_model=PriceHistory,
    summary="Per-store price time series for charting",
)
async def price_history(
    ingredient_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> PriceHistory:
    if await IngredientRepository(session, ctx.org_id).get(ingredient_id) is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Ingredient not found",
            detail=str(ingredient_id),
        )
    rows = await PriceRepository(session, ctx.org_id).history(ingredient_id)
    today = date.today()

    series: dict[uuid.UUID, StoreSeries] = {}
    for r in rows:
        s = series.get(r.store_id)
        if s is None:
            s = StoreSeries(store_id=r.store_id, store_name=r.store_name, points=[])
            series[r.store_id] = s
        days = price_service.age_days(r.observed_at, today)
        s.points.append(
            PriceHistoryPoint(
                observed_at=r.observed_at,
                price_cents=r.price_cents,
                pack_desc=r.pack_desc,
                unit_price_cents=(
                    float(r.unit_price_cents) if r.unit_price_cents is not None else None
                ),
                base_unit=r.base_unit,
                source=r.source,
                age_days=days,
                stale=days > STALE_AFTER_DAYS,
            )
        )
    return PriceHistory(ingredient_id=ingredient_id, series=list(series.values()))
