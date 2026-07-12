"""Store repository — CRUD helpers plus earthdistance radius search."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row

from app.models.store import Store
from app.repositories.base import OrgScopedRepository

# Active stores, optionally annotated with distance (km) from a center point and
# optionally filtered to a radius. Distance uses earthdistance's ll_to_earth /
# earth_distance (meters), served by the gist index on stores(lat,lng).
_LIST_SQL = text(
    """
SELECT s.id, s.name, s.kind, s.address_line, s.city, s.state, s.postal,
       s.lat, s.lng, s.website, s.phone, s.delivers, s.delivery_days,
       s.min_order, s.notes, s.is_active, s.created_at, s.updated_at,
       CASE
         WHEN CAST(:lat AS float8) IS NULL OR s.lat IS NULL OR s.lng IS NULL THEN NULL
         ELSE earth_distance(
                ll_to_earth(s.lat::float8, s.lng::float8),
                ll_to_earth(CAST(:lat AS float8), CAST(:lng AS float8))
              ) / 1000.0
       END AS distance_km
FROM stores s
WHERE s.org_id = :org_id AND s.is_active
  AND (
        CAST(:radius_km AS float8) IS NULL
        OR s.lat IS NULL OR s.lng IS NULL
        OR earth_distance(
             ll_to_earth(s.lat::float8, s.lng::float8),
             ll_to_earth(CAST(:lat AS float8), CAST(:lng AS float8))
           ) <= CAST(:radius_km AS float8) * 1000.0
      )
ORDER BY distance_km ASC NULLS LAST, s.name
"""
)

# When a radius is set, drop stores that have no coordinates (can't be placed).
_LIST_SQL_RADIUS = text(
    """
SELECT s.id, s.name, s.kind, s.address_line, s.city, s.state, s.postal,
       s.lat, s.lng, s.website, s.phone, s.delivers, s.delivery_days,
       s.min_order, s.notes, s.is_active, s.created_at, s.updated_at,
       earth_distance(
         ll_to_earth(s.lat::float8, s.lng::float8),
         ll_to_earth(CAST(:lat AS float8), CAST(:lng AS float8))
       ) / 1000.0 AS distance_km
FROM stores s
WHERE s.org_id = :org_id AND s.is_active
  AND s.lat IS NOT NULL AND s.lng IS NOT NULL
  AND earth_distance(
        ll_to_earth(s.lat::float8, s.lng::float8),
        ll_to_earth(CAST(:lat AS float8), CAST(:lng AS float8))
      ) <= CAST(:radius_km AS float8) * 1000.0
ORDER BY distance_km ASC, s.name
"""
)

_STORE_PRICES_SQL = text(
    """
SELECT DISTINCT ON (pe.ingredient_id)
       pe.ingredient_id, i.canonical_name_en, i.display_name,
       pe.price_cents, pe.pack_desc, pe.pack_qty, pe.pack_unit,
       COALESCE(pe.unit_price_cents_per_kg, pe.unit_price_cents_per_l,
                pe.unit_price_cents_per_each) AS unit_price_cents,
       CASE WHEN pe.unit_price_cents_per_kg IS NOT NULL THEN 'kg'
            WHEN pe.unit_price_cents_per_l IS NOT NULL THEN 'l'
            ELSE 'each' END AS base_unit,
       pe.observed_at, pe.source
FROM price_entries pe
JOIN ingredients i ON i.id = pe.ingredient_id
WHERE pe.org_id = :org_id AND pe.store_id = :store_id
ORDER BY pe.ingredient_id, pe.observed_at DESC, pe.created_at DESC
"""
)


# Ingredients where THIS store currently holds the best (lowest) unit price,
# comparing each store's most recent price per ingredient.
_STORE_WINS_SQL = text(
    """
WITH latest AS (
    SELECT DISTINCT ON (pe.ingredient_id, pe.store_id)
           pe.ingredient_id, pe.store_id,
           COALESCE(pe.unit_price_cents_per_kg, pe.unit_price_cents_per_l,
                    pe.unit_price_cents_per_each) AS unit_price_cents,
           pe.observed_at
    FROM price_entries pe
    WHERE pe.org_id = :org_id
    ORDER BY pe.ingredient_id, pe.store_id, pe.observed_at DESC, pe.created_at DESC
),
best AS (
    SELECT ingredient_id, MIN(unit_price_cents) AS best_price
    FROM latest WHERE unit_price_cents IS NOT NULL GROUP BY ingredient_id
)
SELECT l.ingredient_id, i.canonical_name_en, l.unit_price_cents, l.observed_at
FROM latest l
JOIN best b ON b.ingredient_id = l.ingredient_id AND l.unit_price_cents = b.best_price
JOIN ingredients i ON i.id = l.ingredient_id
WHERE l.store_id = :store_id
ORDER BY i.canonical_name_en
"""
)


class StoreRepository(OrgScopedRepository[Store]):
    model = Store

    async def get_by_name(self, name: str) -> Store | None:
        result = await self.session.execute(self.scoped().where(Store.name == name))
        return result.scalar_one_or_none()

    async def list_stores(
        self,
        *,
        center_lat: float | None = None,
        center_lng: float | None = None,
        radius_km: float | None = None,
    ) -> list[Row[Any]]:
        params = {
            "org_id": self.org_id,
            "lat": center_lat,
            "lng": center_lng,
            "radius_km": radius_km,
        }
        sql = _LIST_SQL_RADIUS if radius_km is not None else _LIST_SQL
        result = await self.session.execute(sql, params)
        return list(result.all())

    async def latest_prices(self, store_id: uuid.UUID) -> list[Row[Any]]:
        result = await self.session.execute(
            _STORE_PRICES_SQL, {"org_id": self.org_id, "store_id": store_id}
        )
        return list(result.all())

    async def wins(self, store_id: uuid.UUID) -> list[Row[Any]]:
        result = await self.session.execute(
            _STORE_WINS_SQL, {"org_id": self.org_id, "store_id": store_id}
        )
        return list(result.all())
