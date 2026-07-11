"""Smoke tests for the org-scoped read endpoints against seeded data."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed import run_seed


@pytest.mark.asyncio
async def test_list_ingredients_and_stores(db_session: AsyncSession, client: AsyncClient) -> None:
    await run_seed(db_session)
    await db_session.commit()

    resp = await client.get("/api/v1/ingredients")
    assert resp.status_code == 200
    ingredients = resp.json()
    assert len(ingredients) == 29
    # Response is org-scoped and carries the multilingual display name.
    names = {i["canonical_name_en"] for i in ingredients}
    assert "Turmeric Powder" in names
    assert all("id" in i and "aliases" in i for i in ingredients)

    resp = await client.get("/api/v1/stores")
    assert resp.status_code == 200
    stores = resp.json()
    assert len(stores) == 6
    chefstore = next(s for s in stores if s["name"] == "CHEF'STORE Redding")
    assert chefstore["postal"] == "96002"
    assert chefstore["kind"] == "cash_and_carry"
