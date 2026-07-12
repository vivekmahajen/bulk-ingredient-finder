"""Price entry: normalization, unit/category warnings, bulk 207, staleness, history."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Category, DefaultUnit, StoreKind
from app.models.ingredient import Ingredient
from app.models.org import Org
from app.models.store import Store


async def _seed(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    org = Org(name="Hari Om")
    session.add(org)
    await session.flush()
    rice = Ingredient(
        org_id=org.id,
        canonical_name_en="Basmati Rice",
        display_name="Basmati Rice",
        category=Category.STAPLE,
        default_unit=DefaultUnit.KG,
    )
    chicken = Ingredient(
        org_id=org.id,
        canonical_name_en="Chicken",
        display_name="Chicken",
        category=Category.PROTEIN,
        default_unit=DefaultUnit.KG,
    )
    store = Store(org_id=org.id, name="CHEF'STORE", kind=StoreKind.CASH_AND_CARRY)
    session.add_all([rice, chicken, store])
    await session.flush()
    await session.commit()
    return rice.id, chicken.id, store.id


@pytest.mark.asyncio
async def test_normalization_20lb_bag(db_session: AsyncSession, client: AsyncClient) -> None:
    rice_id, _, store_id = await _seed(db_session)
    resp = await client.post(
        "/api/v1/prices",
        json={
            "ingredient_id": str(rice_id),
            "store_id": str(store_id),
            "pack_desc": "20 lb bag",
            "pack_qty": 20,
            "pack_unit": "lb",
            "price_cents": 5200,
            "observed_at": "2026-07-01",
            "source": "invoice",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["base_unit"] == "kg"
    assert round(body["unit_price_cents"] / 100, 2) == 5.73
    assert round(body["unit_price_cents_per_kg"] / 100, 2) == 5.73
    assert body["warnings"] == []


@pytest.mark.asyncio
async def test_liters_of_chicken_warns(db_session: AsyncSession, client: AsyncClient) -> None:
    _, chicken_id, store_id = await _seed(db_session)
    resp = await client.post(
        "/api/v1/prices",
        json={
            "ingredient_id": str(chicken_id),
            "store_id": str(store_id),
            "pack_desc": "5 L",
            "pack_qty": 5,
            "pack_unit": "l",
            "price_cents": 3000,
            "source": "shelf",
        },
    )
    # Mismatch is a warning, not an error — the entry still saves (201).
    assert resp.status_code == 201, resp.text
    assert resp.json()["warnings"], "expected a unit/category warning"


@pytest.mark.asyncio
async def test_validation_rejects_nonpositive(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    rice_id, _, store_id = await _seed(db_session)
    resp = await client.post(
        "/api/v1/prices",
        json={
            "ingredient_id": str(rice_id),
            "store_id": str(store_id),
            "pack_desc": "bad",
            "pack_qty": 0,
            "pack_unit": "kg",
            "price_cents": -1,
            "source": "shelf",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_partial_failure_207(db_session: AsyncSession, client: AsyncClient) -> None:
    rice_id, _, store_id = await _seed(db_session)
    good = {
        "ingredient_id": str(rice_id),
        "store_id": str(store_id),
        "pack_desc": "20 lb",
        "pack_qty": 20,
        "pack_unit": "lb",
        "price_cents": 5200,
        "source": "invoice",
    }
    bad_ingredient = {**good, "ingredient_id": str(uuid.uuid4())}
    resp = await client.post("/api/v1/prices/bulk", json={"entries": [good, bad_ingredient, good]})
    assert resp.status_code == 207, resp.text
    body = resp.json()
    assert body["created"] == 2
    assert body["failed"] == 1
    assert [r["ok"] for r in body["results"]] == [True, False, True]
    assert body["results"][1]["error"] == "Unknown ingredient_id"


@pytest.mark.asyncio
async def test_stale_flag(db_session: AsyncSession, client: AsyncClient) -> None:
    rice_id, _, store_id = await _seed(db_session)
    old = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    fresh = dt.date.today().isoformat()
    for observed, expect_stale in [(old, True), (fresh, False)]:
        resp = await client.post(
            "/api/v1/prices",
            json={
                "ingredient_id": str(rice_id),
                "store_id": str(store_id),
                "pack_desc": "20 lb",
                "pack_qty": 20,
                "pack_unit": "lb",
                "price_cents": 5200,
                "observed_at": observed,
                "source": "invoice",
            },
        )
        assert resp.json()["stale"] is expect_stale


@pytest.mark.asyncio
async def test_price_history_series(db_session: AsyncSession, client: AsyncClient) -> None:
    rice_id, _, store_id = await _seed(db_session)
    for day, cents in [("2026-06-01", 5000), ("2026-07-01", 5200)]:
        await client.post(
            "/api/v1/prices",
            json={
                "ingredient_id": str(rice_id),
                "store_id": str(store_id),
                "pack_desc": "20 lb",
                "pack_qty": 20,
                "pack_unit": "lb",
                "price_cents": cents,
                "observed_at": day,
                "source": "invoice",
            },
        )
    resp = await client.get(f"/api/v1/ingredients/{rice_id}/price-history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["series"]) == 1
    points = body["series"][0]["points"]
    assert [p["observed_at"] for p in points] == ["2026-06-01", "2026-07-01"]  # ascending


@pytest.mark.asyncio
async def test_list_prices_pagination(db_session: AsyncSession, client: AsyncClient) -> None:
    rice_id, _, store_id = await _seed(db_session)
    for i in range(3):
        await client.post(
            "/api/v1/prices",
            json={
                "ingredient_id": str(rice_id),
                "store_id": str(store_id),
                "pack_desc": f"pack {i}",
                "pack_qty": 20,
                "pack_unit": "lb",
                "price_cents": 5000 + i,
                "source": "invoice",
            },
        )
    resp = await client.get("/api/v1/prices", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
