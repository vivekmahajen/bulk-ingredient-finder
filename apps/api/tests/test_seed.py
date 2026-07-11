"""Seed correctness + idempotency."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredient import Ingredient
from app.models.org import Org
from app.models.store import Store
from scripts.seed import run_seed


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    first = await run_seed(db_session)
    await db_session.commit()
    assert first == {"org": 1, "user": 1, "ingredients": 29, "stores": 6}

    second = await run_seed(db_session)
    await db_session.commit()
    assert second == {"org": 0, "user": 0, "ingredients": 0, "stores": 0}

    orgs = await db_session.scalar(select(func.count()).select_from(Org))
    ingredients = await db_session.scalar(select(func.count()).select_from(Ingredient))
    stores = await db_session.scalar(select(func.count()).select_from(Store))
    assert (orgs, ingredients, stores) == (1, 29, 6)
