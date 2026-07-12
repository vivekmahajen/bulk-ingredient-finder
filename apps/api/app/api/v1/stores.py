"""Store endpoints (PR-5): CRUD + geocoding + radius search + prices/wins."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.models.store import Store
from app.repositories.stores import StoreRepository
from app.repositories.tenancy import OrgRepository
from app.schemas.store import (
    StoreCreate,
    StorePriceRow,
    StoreRead,
    StoreUpdate,
    StoreWin,
)
from app.services import audit
from app.services.geocode import GeocodeService, get_geocode_service

router = APIRouter(prefix="/stores", tags=["stores"])


def _read_from_orm(store: Store, distance_km: float | None = None) -> StoreRead:
    data = StoreRead.model_validate(store)
    data.distance_km = distance_km
    data.geocoded = store.lat is not None and store.lng is not None
    return data


def _read_from_row(row: Row[Any]) -> StoreRead:
    mapping = dict(row._mapping)
    distance = mapping.pop("distance_km", None)
    read = StoreRead.model_validate(mapping)
    read.distance_km = float(distance) if distance is not None else None
    read.geocoded = read.lat is not None and read.lng is not None
    return read


def _parse_near(near: str | None) -> tuple[float, float] | None:
    if not near:
        return None
    try:
        lat_s, lng_s = near.split(",")
        return float(lat_s), float(lng_s)
    except (ValueError, TypeError) as exc:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Invalid 'near'",
            detail="near must be 'lat,lng', e.g. near=41.31,-122.32",
        ) from exc


@router.get("", response_model=list[StoreRead], summary="List stores (radius-aware)")
async def list_stores(
    near: str | None = Query(default=None, description="Center as 'lat,lng'"),
    radius_km: float | None = Query(default=None, ge=0),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[StoreRead]:
    center = _parse_near(near)
    # Default the center to the org's home location when 'near' isn't supplied.
    if center is None:
        org = await OrgRepository(session).get(ctx.org_id)
        if org and org.home_lat is not None and org.home_lng is not None:
            center = (float(org.home_lat), float(org.home_lng))
    center_lat, center_lng = center if center else (None, None)
    rows = await StoreRepository(session, ctx.org_id).list_stores(
        center_lat=center_lat, center_lng=center_lng, radius_km=radius_km
    )
    return [_read_from_row(r) for r in rows]


@router.post(
    "", response_model=StoreRead, status_code=status.HTTP_201_CREATED, summary="Add a store"
)
async def create_store(
    payload: StoreCreate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    geocoder: GeocodeService = Depends(get_geocode_service),
) -> StoreRead:
    store = Store(org_id=ctx.org_id, **payload.model_dump())
    # Geocode when coordinates weren't supplied but an address was. Failure is
    # non-fatal: the store still saves and the UI offers manual lat/lng entry.
    if store.lat is None and store.lng is None and (store.address_line or store.city):
        address = ", ".join(
            p for p in [store.address_line, store.city, store.state, store.postal] if p
        )
        result = await geocoder.locate(address)
        if result is not None:
            store.lat = result.lat
            store.lng = result.lng
    session.add(store)
    await session.flush()
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="store.create",
        entity="store",
        entity_id=store.id,
        meta={"name": store.name, "geocoded": store.lat is not None},
    )
    await session.commit()
    await session.refresh(store)
    return _read_from_orm(store)


@router.get("/{store_id}", response_model=StoreRead, summary="Get one store")
async def get_store(
    store_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> StoreRead:
    store = await StoreRepository(session, ctx.org_id).get(store_id)
    if store is None or not store.is_active:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Store not found", detail=str(store_id)
        )
    return _read_from_orm(store)


@router.patch("/{store_id}", response_model=StoreRead, summary="Update a store")
async def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    geocoder: GeocodeService = Depends(get_geocode_service),
) -> StoreRead:
    repo = StoreRepository(session, ctx.org_id)
    store = await repo.get(store_id)
    if store is None or not store.is_active:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Store not found", detail=str(store_id)
        )
    changes = payload.model_dump(exclude_unset=True)
    address_changed = any(k in changes for k in ("address_line", "city", "state", "postal"))
    for key, value in changes.items():
        setattr(store, key, value)
    # Re-geocode if the address changed and no explicit coordinates were given.
    if address_changed and "lat" not in changes and "lng" not in changes:
        address = ", ".join(
            p for p in [store.address_line, store.city, store.state, store.postal] if p
        )
        result = await geocoder.locate(address)
        if result is not None:
            store.lat = result.lat
            store.lng = result.lng
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="store.update",
        entity="store",
        entity_id=store.id,
        meta={"fields": list(changes.keys())},
    )
    await session.commit()
    await session.refresh(store)
    return _read_from_orm(store)


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft-delete a store")
async def delete_store(
    store_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = StoreRepository(session, ctx.org_id)
    store = await repo.get(store_id)
    if store is None or not store.is_active:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Store not found", detail=str(store_id)
        )
    store.is_active = False
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="store.delete",
        entity="store",
        entity_id=store.id,
        meta={"name": store.name},
    )
    await session.commit()


@router.get(
    "/{store_id}/prices",
    response_model=list[StorePriceRow],
    summary="Latest price per ingredient at this store",
)
async def store_prices(
    store_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[StorePriceRow]:
    repo = StoreRepository(session, ctx.org_id)
    if await repo.get(store_id) is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Store not found", detail=str(store_id)
        )
    rows = await repo.latest_prices(store_id)
    return [StorePriceRow.model_validate(dict(r._mapping)) for r in rows]


@router.get(
    "/{store_id}/wins",
    response_model=list[StoreWin],
    summary="Ingredients this store currently wins on (best price)",
)
async def store_wins(
    store_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[StoreWin]:
    repo = StoreRepository(session, ctx.org_id)
    if await repo.get(store_id) is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Store not found", detail=str(store_id)
        )
    rows = await repo.wins(store_id)
    return [StoreWin.model_validate(dict(r._mapping)) for r in rows]
