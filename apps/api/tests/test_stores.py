"""Stores: geocoding, radius/earthdistance search, soft-delete, prices, wins."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Category, DefaultUnit, PackUnit, PriceSource, StoreKind
from app.models.ingredient import Ingredient
from app.models.org import Org
from app.models.price import PriceEntry
from app.models.store import Store
from app.services.geocode import GeocodeResult, GeocodeService, get_geocode_service

# Reference coordinates (lat, lng).
MOUNT_SHASTA = (41.31, -122.32)
REDDING = (40.5865, -122.3917)  # ~80–96 km south of Shasta
SACRAMENTO = (38.5816, -121.4944)  # ~300+ km south of Shasta


async def _seed_org(session: AsyncSession, *, home: tuple[float, float] | None = None) -> uuid.UUID:
    org = Org(name="Hari Om")
    if home:
        org.home_lat, org.home_lng = home
    session.add(org)
    await session.flush()
    return org.id


class _FixedGeocoder:
    name = "fixed"

    def __init__(self, result: GeocodeResult | None) -> None:
        self._result = result

    async def geocode(self, address: str) -> GeocodeResult | None:
        return self._result


@pytest.mark.asyncio
async def test_geocode_failure_still_saves_store(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _seed_org(db_session)
    await db_session.commit()
    # NullGeocodeProvider is the default → returns None (geocode "outage").
    resp = await client.post(
        "/api/v1/stores",
        json={"name": "Raja Foods", "kind": "ethnic_wholesale", "city": "Skokie", "state": "IL"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["lat"] is None and body["lng"] is None
    assert body["geocoded"] is False  # UI can then offer manual lat/lng entry


@pytest.mark.asyncio
async def test_geocode_success_sets_coords(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _seed_org(db_session)
    await db_session.commit()
    app.dependency_overrides[get_geocode_service] = lambda: GeocodeService(
        _FixedGeocoder(GeocodeResult(lat=REDDING[0], lng=REDDING[1]))
    )
    resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "CHEF'STORE Redding",
            "kind": "cash_and_carry",
            "address_line": "1152 Hartnell Ave",
            "city": "Redding",
            "state": "CA",
            "postal": "96002",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["geocoded"] is True
    assert round(body["lat"], 2) == round(REDDING[0], 2)


@pytest.mark.asyncio
async def test_radius_search_and_distance_sort(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    org_id = await _seed_org(db_session, home=MOUNT_SHASTA)
    db_session.add_all(
        [
            Store(
                org_id=org_id,
                name="CHEF'STORE Redding",
                kind=StoreKind.CASH_AND_CARRY,
                lat=REDDING[0],
                lng=REDDING[1],
            ),
            Store(
                org_id=org_id,
                name="Sysco Sacramento",
                kind=StoreKind.BROADLINE,
                lat=SACRAMENTO[0],
                lng=SACRAMENTO[1],
            ),
        ]
    )
    await db_session.commit()

    # Radius 150 km from Shasta → Redding only.
    resp = await client.get(
        "/api/v1/stores", params={"near": f"{MOUNT_SHASTA[0]},{MOUNT_SHASTA[1]}", "radius_km": 150}
    )
    assert resp.status_code == 200
    stores = resp.json()
    names = [s["name"] for s in stores]
    assert names == ["CHEF'STORE Redding"]
    assert stores[0]["distance_km"] < 150

    # No radius → both, sorted by distance (Redding before Sacramento).
    resp = await client.get(
        "/api/v1/stores", params={"near": f"{MOUNT_SHASTA[0]},{MOUNT_SHASTA[1]}"}
    )
    ordered = [s["name"] for s in resp.json()]
    assert ordered == ["CHEF'STORE Redding", "Sysco Sacramento"]
    dists = [s["distance_km"] for s in resp.json()]
    assert dists[0] < dists[1]
    assert dists[1] > 250  # Sacramento is far


@pytest.mark.asyncio
async def test_distance_defaults_to_org_home(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session, home=MOUNT_SHASTA)
    db_session.add(
        Store(
            org_id=org_id,
            name="CHEF'STORE Redding",
            kind=StoreKind.CASH_AND_CARRY,
            lat=REDDING[0],
            lng=REDDING[1],
        )
    )
    await db_session.commit()
    # No 'near' → distance is measured from the org's home location.
    resp = await client.get("/api/v1/stores")
    assert resp.json()[0]["distance_km"] is not None
    assert resp.json()[0]["distance_km"] < 150


@pytest.mark.asyncio
async def test_soft_delete(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session)
    store = Store(org_id=org_id, name="Temp", kind=StoreKind.RETAIL)
    db_session.add(store)
    await db_session.commit()
    sid = str(store.id)

    assert (await client.delete(f"/api/v1/stores/{sid}")).status_code == 204
    assert (await client.get(f"/api/v1/stores/{sid}")).status_code == 404
    assert [s["name"] for s in (await client.get("/api/v1/stores")).json()] == []


@pytest.mark.asyncio
async def test_store_prices_and_wins(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session)
    rice = Ingredient(
        org_id=org_id,
        canonical_name_en="Basmati Rice",
        display_name="Basmati Rice",
        category=Category.STAPLE,
        default_unit=DefaultUnit.KG,
    )
    cheap = Store(org_id=org_id, name="Cheap", kind=StoreKind.CASH_AND_CARRY)
    pricey = Store(org_id=org_id, name="Pricey", kind=StoreKind.RETAIL)
    db_session.add_all([rice, cheap, pricey])
    await db_session.flush()
    db_session.add_all(
        [
            PriceEntry(
                org_id=org_id,
                ingredient_id=rice.id,
                store_id=cheap.id,
                pack_desc="20 lb",
                pack_qty=Decimal(20),
                pack_unit=PackUnit.LB,
                price_cents=4000,
                observed_at=dt.date(2026, 7, 1),
                source=PriceSource.INVOICE,
            ),
            PriceEntry(
                org_id=org_id,
                ingredient_id=rice.id,
                store_id=pricey.id,
                pack_desc="20 lb",
                pack_qty=Decimal(20),
                pack_unit=PackUnit.LB,
                price_cents=6000,
                observed_at=dt.date(2026, 7, 1),
                source=PriceSource.SHELF,
            ),
        ]
    )
    await db_session.commit()

    prices = (await client.get(f"/api/v1/stores/{cheap.id}/prices")).json()
    assert len(prices) == 1
    assert prices[0]["canonical_name_en"] == "Basmati Rice"

    # The cheaper store wins on rice; the pricier one does not.
    cheap_wins = (await client.get(f"/api/v1/stores/{cheap.id}/wins")).json()
    pricey_wins = (await client.get(f"/api/v1/stores/{pricey.id}/wins")).json()
    assert [w["canonical_name_en"] for w in cheap_wins] == ["Basmati Rice"]
    assert pricey_wins == []
