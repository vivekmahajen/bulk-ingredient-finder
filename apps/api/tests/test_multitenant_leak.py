"""Cross-tenant leak suite: org A must never read org B's data (every GET)."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import RequestContext, get_context
from app.models.enums import Category, DefaultUnit, PackUnit, PriceSource, StoreKind
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.org import Org
from app.models.price import PriceEntry
from app.models.store import Store
from app.models.user import User


@dataclass
class Tenant:
    org_id: uuid.UUID
    user_id: uuid.UUID
    ingredient_id: uuid.UUID
    store_id: uuid.UUID


async def _make_tenant(session: AsyncSession, name: str) -> Tenant:
    org = Org(name=name)
    session.add(org)
    await session.flush()
    user = User(org_id=org.id, email=f"{name}@x.example", display_name=name)
    ing = Ingredient(
        org_id=org.id,
        canonical_name_en=f"{name} Rice",
        display_name=f"{name} Rice",
        category=Category.STAPLE,
        default_unit=DefaultUnit.KG,
        aliases=[
            IngredientAlias(org_id=org.id, alias=f"{name}-chawal", lang="hi-Latn", kind="synonym")
        ],
    )
    store = Store(org_id=org.id, name=f"{name} Store", kind=StoreKind.CASH_AND_CARRY)
    session.add_all([user, ing, store])
    await session.flush()
    session.add(
        PriceEntry(
            org_id=org.id,
            ingredient_id=ing.id,
            store_id=store.id,
            pack_desc="1 kg",
            pack_qty=Decimal(1),
            pack_unit=PackUnit.KG,
            price_cents=500,
            observed_at=dt.date.today(),
            source=PriceSource.INVOICE,
        )
    )
    return Tenant(org.id, user.id, ing.id, store.id)


@pytest.mark.asyncio
async def test_lists_are_org_scoped(db_session: AsyncSession, app, client: AsyncClient) -> None:
    a = await _make_tenant(db_session, "AAA")
    await _make_tenant(db_session, "BBB")
    await db_session.commit()
    app.dependency_overrides[get_context] = lambda: RequestContext(a.org_id, a.user_id)

    # List endpoints only ever return the acting org's rows.
    ings = (await client.get("/api/v1/ingredients")).json()
    assert {i["canonical_name_en"] for i in ings} == {"AAA Rice"}

    stores = (await client.get("/api/v1/stores")).json()
    assert {s["name"] for s in stores} == {"AAA Store"}

    prices = (await client.get("/api/v1/prices")).json()["items"]
    assert len(prices) == 1

    # "chawal" fuzzy-matches both orgs' aliases, but search is org-scoped to A.
    hits = (await client.get("/api/v1/search/ingredients", params={"q": "chawal"})).json()
    assert {r["canonical_name_en"] for r in hits["results"]} == {"AAA Rice"}


@pytest.mark.asyncio
async def test_by_id_reads_of_other_org_404(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    a = await _make_tenant(db_session, "AAA")
    b = await _make_tenant(db_session, "BBB")
    await db_session.commit()
    app.dependency_overrides[get_context] = lambda: RequestContext(a.org_id, a.user_id)

    # Every by-id GET of org B's resources, while acting as org A, must 404.
    other_org_gets = [
        f"/api/v1/ingredients/{b.ingredient_id}",
        f"/api/v1/ingredients/{b.ingredient_id}/price-history",
        f"/api/v1/stores/{b.store_id}",
        f"/api/v1/stores/{b.store_id}/prices",
        f"/api/v1/stores/{b.store_id}/wins",
    ]
    for path in other_org_gets:
        resp = await client.get(path)
        assert resp.status_code == 404, f"{path} leaked org B (status {resp.status_code})"

    # Compare scoped to A can't pull in B's ingredient.
    resp = await client.get("/api/v1/compare", params={"ingredient_ids": [str(b.ingredient_id)]})
    assert resp.status_code == 404

    # A's own resources remain reachable (sanity — scoping isn't just blanket-404).
    assert (await client.get(f"/api/v1/ingredients/{a.ingredient_id}")).status_code == 200
    assert (await client.get(f"/api/v1/stores/{a.store_id}")).status_code == 200
