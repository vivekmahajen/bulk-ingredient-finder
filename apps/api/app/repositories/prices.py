"""Price-entry repository."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.engine import Row

from app.models.price import PriceEntry
from app.repositories.base import OrgScopedRepository

_HISTORY_SQL = text(
    """
SELECT pe.store_id, s.name AS store_name, pe.observed_at, pe.price_cents, pe.pack_desc,
       pe.pack_qty, pe.pack_unit,
       COALESCE(pe.unit_price_cents_per_kg, pe.unit_price_cents_per_l,
                pe.unit_price_cents_per_each) AS unit_price_cents,
       CASE WHEN pe.unit_price_cents_per_kg IS NOT NULL THEN 'kg'
            WHEN pe.unit_price_cents_per_l IS NOT NULL THEN 'l'
            ELSE 'each' END AS base_unit,
       pe.source
FROM price_entries pe
JOIN stores s ON s.id = pe.store_id
WHERE pe.org_id = :org_id AND pe.ingredient_id = :ingredient_id
ORDER BY s.name, pe.observed_at ASC, pe.created_at ASC
"""
)


class PriceRepository(OrgScopedRepository[PriceEntry]):
    model = PriceEntry

    async def list_prices(
        self,
        *,
        ingredient_id: uuid.UUID | None = None,
        store_id: uuid.UUID | None = None,
        since: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PriceEntry], int]:
        stmt = self.scoped()
        if ingredient_id is not None:
            stmt = stmt.where(PriceEntry.ingredient_id == ingredient_id)
        if store_id is not None:
            stmt = stmt.where(PriceEntry.store_id == store_id)
        if since is not None:
            stmt = stmt.where(PriceEntry.observed_at >= since)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self.session.execute(count_stmt)).scalar_one())

        page = stmt.order_by(PriceEntry.observed_at.desc(), PriceEntry.created_at.desc())
        page = page.limit(limit).offset(offset)
        rows = list((await self.session.execute(page)).scalars().all())
        return rows, total

    async def history(self, ingredient_id: uuid.UUID) -> list[Row[Any]]:
        result = await self.session.execute(
            _HISTORY_SQL, {"org_id": self.org_id, "ingredient_id": ingredient_id}
        )
        return list(result.all())
