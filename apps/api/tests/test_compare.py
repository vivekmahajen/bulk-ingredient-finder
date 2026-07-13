"""Compare: ranking golden file, radius/delivery matrix, frequency-run, savings."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    Category,
    DefaultUnit,
    PackUnit,
    PriceSource,
    PurchaseFrequency,
    StoreKind,
)
from app.models.ingredient import Ingredient
from app.models.org import Org
from app.models.price import PriceEntry
from app.models.store import Store

# Golden fixture — 3 ingredients × 4 stores, prices in cents per kg (1 kg packs).
PRICES = {
    "Rice": {"A": 500, "B": 520, "C": 480, "D": 600},
    "Dal": {"A": 300, "B": 290, "C": 310, "D": 280},
    "Oil": {"A": 800, "B": 750, "C": 900, "D": 600},
}


async def _seed_golden(session: AsyncSession) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    org = Org(name="Hari Om")
    session.add(org)
    await session.flush()

    stores = {
        name: Store(org_id=org.id, name=name, kind=StoreKind.CASH_AND_CARRY) for name in "ABCD"
    }
    ings = {
        name: Ingredient(
            org_id=org.id,
            canonical_name_en=name,
            display_name=name,
            category=Category.STAPLE,
            default_unit=DefaultUnit.KG,
            purchase_frequency=PurchaseFrequency.WEEKLY,
        )
        for name in PRICES
    }
    session.add_all([*stores.values(), *ings.values()])
    await session.flush()

    for iname, per_store in PRICES.items():
        for sname, cents in per_store.items():
            session.add(
                PriceEntry(
                    org_id=org.id,
                    ingredient_id=ings[iname].id,
                    store_id=stores[sname].id,
                    pack_desc="1 kg",
                    pack_qty=Decimal(1),
                    pack_unit=PackUnit.KG,
                    price_cents=cents,
                    observed_at=dt.date.today(),
                    source=PriceSource.INVOICE,
                )
            )
    await session.commit()
    return org.id, {name: ings[name].id for name in PRICES}


@pytest.mark.asyncio
async def test_radius_ignored_without_home_location(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    # A supplier with no coordinates, no delivery, and an org with no home
    # location: a radius should NOT hide it (we can't compute distance), and a
    # note should explain how to enable distance filtering.
    org = Org(name="No Home")
    db_session.add(org)
    await db_session.flush()
    store = Store(org_id=org.id, name="Local Wholesaler", kind=StoreKind.CASH_AND_CARRY)
    rice = Ingredient(
        org_id=org.id,
        canonical_name_en="Rice",
        display_name="Rice",
        category=Category.STAPLE,
        default_unit=DefaultUnit.KG,
        purchase_frequency=PurchaseFrequency.WEEKLY,
    )
    db_session.add_all([store, rice])
    await db_session.flush()
    db_session.add(
        PriceEntry(
            org_id=org.id,
            ingredient_id=rice.id,
            store_id=store.id,
            pack_desc="1 kg",
            pack_qty=Decimal(1),
            pack_unit=PackUnit.KG,
            price_cents=500,
            observed_at=dt.date.today(),
            source=PriceSource.INVOICE,
        )
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/compare",
        params={"ingredient_ids": [str(rice.id)], "radius_km": 25, "include_delivery": "false"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    options = body["ingredients"][0]["options"]
    assert [o["store_name"] for o in options] == ["Local Wholesaler"]
    assert any("set your location" in n.lower() for n in body["notes"])


@pytest.mark.asyncio
async def test_ranking_golden(db_session: AsyncSession, client: AsyncClient) -> None:
    _, ids = await _seed_golden(db_session)
    resp = await client.get(
        "/api/v1/compare", params={"ingredient_ids": [str(v) for v in ids.values()]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_name = {r["canonical_name_en"]: r for r in body["ingredients"]}

    # Cheapest store per ingredient.
    rice = by_name["Rice"]
    assert [o["store_name"] for o in rice["options"]] == ["C", "A", "B", "D"]
    assert rice["options"][0]["unit_price_cents"] == 480
    # Rice cheapest (480) vs worst (600) → 20% savings.
    assert round(rice["options"][0]["savings_vs_worst_pct"]) == 20
    assert rice["options"][0]["confidence"] == "high"  # invoice, age 0

    assert by_name["Dal"]["options"][0]["store_name"] == "D"
    assert by_name["Oil"]["options"][0]["store_name"] == "D"


@pytest.mark.asyncio
async def test_basket_math_to_the_cent(db_session: AsyncSession, client: AsyncClient) -> None:
    _, ids = await _seed_golden(db_session)
    resp = await client.get(
        "/api/v1/compare", params={"ingredient_ids": [str(v) for v in ids.values()]}
    )
    basket = resp.json()["basket_summary"]

    # best-per-item = 480 + 280 + 600 = 1360
    assert basket["best_per_item_total_cents"] == 1360
    # single cheapest all-carrying store = D at 600+280+600 = 1480
    assert basket["single_store"]["store_name"] == "D"
    assert basket["single_store"]["total_cents"] == 1480
    assert basket["savings_best_vs_single_cents"] == 120
    # split: primary D, move Rice to C (saves 120) → total 1360
    split = basket["split"]
    assert split["primary"]["store_name"] == "D"
    assert split["secondary"]["store_name"] == "C"
    assert split["total_cents"] == 1360
    assert split["savings_vs_single_cents"] == 120


@pytest.mark.asyncio
async def test_quantities_scale_savings(db_session: AsyncSession, client: AsyncClient) -> None:
    _, ids = await _seed_golden(db_session)
    # 10 kg of Rice/Dal/Oil each → savings scale ×10.
    resp = await client.post(
        "/api/v1/compare",
        json={
            "ingredient_ids": [str(v) for v in ids.values()],
            "quantities": {str(v): 10 for v in ids.values()},
        },
    )
    basket = resp.json()["basket_summary"]
    assert basket["best_per_item_total_cents"] == 13600  # 1360 × 10
    assert basket["single_store"]["total_cents"] == 14800
    assert basket["savings_best_vs_single_cents"] == 1200


@pytest.mark.asyncio
async def test_frequency_run(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id, _ = await _seed_golden(db_session)
    # Add a monthly ingredient that must NOT appear in the weekly run.
    db_session.add(
        Ingredient(
            org_id=org_id,
            canonical_name_en="Turmeric",
            display_name="Turmeric",
            category=Category.SPICE,
            default_unit=DefaultUnit.KG,
            purchase_frequency=PurchaseFrequency.MONTHLY,
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/compare/frequency-run", params={"frequency": "weekly"})
    names = {r["canonical_name_en"] for r in resp.json()["ingredients"]}
    assert names == {"Rice", "Dal", "Oil"}


@pytest.mark.asyncio
async def test_radius_and_delivery_matrix(db_session: AsyncSession, client: AsyncClient) -> None:
    org = Org(name="Hari Om", home_lat=41.31, home_lng=-122.32)  # Mount Shasta
    session = db_session
    session.add(org)
    await session.flush()
    near = Store(
        org_id=org.id, name="Near", kind=StoreKind.CASH_AND_CARRY, lat=40.5865, lng=-122.3917
    )
    far = Store(org_id=org.id, name="Far", kind=StoreKind.BROADLINE, lat=38.5816, lng=-121.4944)
    far_delivers = Store(
        org_id=org.id,
        name="FarDelivers",
        kind=StoreKind.ONLINE,
        lat=38.5,
        lng=-121.5,
        delivers=True,
    )
    rice = Ingredient(
        org_id=org.id,
        canonical_name_en="Rice",
        display_name="Rice",
        category=Category.STAPLE,
        default_unit=DefaultUnit.KG,
    )
    session.add_all([near, far, far_delivers, rice])
    await session.flush()
    for store, cents in [(near, 500), (far, 400), (far_delivers, 450)]:
        session.add(
            PriceEntry(
                org_id=org.id,
                ingredient_id=rice.id,
                store_id=store.id,
                pack_desc="1 kg",
                pack_qty=Decimal(1),
                pack_unit=PackUnit.KG,
                price_cents=cents,
                observed_at=dt.date.today(),
                source=PriceSource.INVOICE,
            )
        )
    await session.commit()

    # radius 150 km, no delivery → only Near.
    resp = await client.get(
        "/api/v1/compare",
        params={"ingredient_ids": [str(rice.id)], "radius_km": 150, "include_delivery": "false"},
    )
    stores = {o["store_name"] for o in resp.json()["ingredients"][0]["options"]}
    assert stores == {"Near"}

    # radius 150 km + delivery → Near and FarDelivers (Far excluded).
    resp = await client.get(
        "/api/v1/compare",
        params={"ingredient_ids": [str(rice.id)], "radius_km": 150, "include_delivery": "true"},
    )
    stores = {o["store_name"] for o in resp.json()["ingredients"][0]["options"]}
    assert stores == {"Near", "FarDelivers"}
