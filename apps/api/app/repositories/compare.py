"""Compare repository: latest price per (ingredient, store) for a candidate set."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredient import Ingredient
from app.models.price import PriceEntry
from app.models.store import Store

_UNIT_PRICE = func.coalesce(
    PriceEntry.unit_price_cents_per_kg,
    PriceEntry.unit_price_cents_per_l,
    PriceEntry.unit_price_cents_per_each,
)

_BASE_UNIT = case(
    (PriceEntry.unit_price_cents_per_kg.isnot(None), "kg"),
    (PriceEntry.unit_price_cents_per_l.isnot(None), "l"),
    else_="each",
)


class CompareRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def ingredients_by_ids(self, ids: list[uuid.UUID]) -> list[Ingredient]:
        stmt = (
            select(Ingredient)
            .where(Ingredient.org_id == self.org_id, Ingredient.is_active.is_(True))
            .where(Ingredient.id.in_(ids))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def ingredients_by_frequency(self, frequency: str) -> list[Ingredient]:
        stmt = (
            select(Ingredient)
            .where(Ingredient.org_id == self.org_id, Ingredient.is_active.is_(True))
            .where(Ingredient.purchase_frequency == frequency)
            .order_by(Ingredient.canonical_name_en)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest_per_store(
        self, ingredient_ids: list[uuid.UUID], store_ids: list[uuid.UUID]
    ) -> list[Row[Any]]:
        """Most recent price for each (ingredient, store) pair in the candidate sets."""
        if not ingredient_ids or not store_ids:
            return []
        stmt = (
            select(
                PriceEntry.ingredient_id,
                PriceEntry.store_id,
                Store.name.label("store_name"),
                Store.kind.label("store_kind"),
                Store.delivers,
                PriceEntry.brand,
                PriceEntry.price_cents,
                PriceEntry.pack_desc,
                _UNIT_PRICE.label("unit_price_cents"),
                _BASE_UNIT.label("base_unit"),
                PriceEntry.observed_at,
                PriceEntry.source,
            )
            .join(Store, Store.id == PriceEntry.store_id)
            .where(PriceEntry.org_id == self.org_id)
            .where(PriceEntry.ingredient_id.in_(ingredient_ids))
            .where(PriceEntry.store_id.in_(store_ids))
            .distinct(PriceEntry.ingredient_id, PriceEntry.store_id)
            .order_by(
                PriceEntry.ingredient_id,
                PriceEntry.store_id,
                PriceEntry.observed_at.desc(),
                PriceEntry.created_at.desc(),
            )
        )
        return list((await self.session.execute(stmt)).all())
