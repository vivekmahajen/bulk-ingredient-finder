"""Search repository — trigram + alias union with ranking and best-price join.

Raw SQL (in the repository layer, org-scoped by ``:org_id``) so we can lean on
pg_trgm's ``%`` operator and the GIN(unaccent) indexes. Candidates come from a
UNION of canonical-name and alias matches; each ingredient keeps its best-scoring
match. A LATERAL join attaches the cheapest current unit price per ingredient.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

# Scoring: exact = 1.0, prefix = 0.9, else 0.3 + 0.5*similarity (∈ [0.3, 0.8]).
_SEARCH_SQL = text(
    """
WITH q AS (SELECT f_unaccent(lower(:q)) AS qn),
cand AS (
    SELECT i.id AS ingredient_id,
           CASE
             WHEN f_unaccent(lower(i.canonical_name_en)) = (SELECT qn FROM q) THEN 1.0
             WHEN f_unaccent(lower(i.canonical_name_en)) LIKE (SELECT qn FROM q) || '%' THEN 0.9
             ELSE 0.3 + 0.5 * similarity(f_unaccent(lower(i.canonical_name_en)), (SELECT qn FROM q))
           END AS score,
           i.canonical_name_en AS matched_text,
           'canonical' AS matched_kind
    FROM ingredients i
    WHERE i.org_id = :org_id AND i.is_active
      AND (f_unaccent(lower(i.canonical_name_en)) % (SELECT qn FROM q)
           OR f_unaccent(lower(i.canonical_name_en)) LIKE (SELECT qn FROM q) || '%')
    UNION ALL
    SELECT a.ingredient_id,
           CASE
             WHEN f_unaccent(lower(a.alias)) = (SELECT qn FROM q) THEN 1.0
             WHEN f_unaccent(lower(a.alias)) LIKE (SELECT qn FROM q) || '%' THEN 0.9
             ELSE 0.3 + 0.5 * similarity(f_unaccent(lower(a.alias)), (SELECT qn FROM q))
           END AS score,
           a.alias AS matched_text,
           'alias' AS matched_kind
    FROM ingredient_aliases a
    WHERE a.org_id = :org_id
      AND (f_unaccent(lower(a.alias)) % (SELECT qn FROM q)
           OR f_unaccent(lower(a.alias)) LIKE (SELECT qn FROM q) || '%')
),
best AS (
    SELECT DISTINCT ON (ingredient_id)
           ingredient_id, score, matched_text, matched_kind
    FROM cand
    ORDER BY ingredient_id, score DESC, matched_kind
)
SELECT i.id, i.canonical_name_en, i.display_name, i.source_lang,
       i.category::text AS category, i.default_unit::text AS default_unit,
       i.purchase_frequency::text AS purchase_frequency, i.needs_review,
       b.score, b.matched_text, b.matched_kind,
       lp.price_cents, lp.unit_price_cents, lp.base_unit, lp.store_name, lp.observed_at
FROM best b
JOIN ingredients i ON i.id = b.ingredient_id
LEFT JOIN LATERAL (
    SELECT pe.price_cents,
           COALESCE(pe.unit_price_cents_per_kg, pe.unit_price_cents_per_l,
                    pe.unit_price_cents_per_each) AS unit_price_cents,
           CASE WHEN pe.unit_price_cents_per_kg IS NOT NULL THEN 'kg'
                WHEN pe.unit_price_cents_per_l IS NOT NULL THEN 'l'
                ELSE 'each' END AS base_unit,
           s.name AS store_name, pe.observed_at
    FROM price_entries pe JOIN stores s ON s.id = pe.store_id
    WHERE pe.ingredient_id = i.id AND pe.org_id = :org_id
    ORDER BY COALESCE(pe.unit_price_cents_per_kg, pe.unit_price_cents_per_l,
                      pe.unit_price_cents_per_each) ASC NULLS LAST
    LIMIT 1
) lp ON true
WHERE (CAST(:category AS text) IS NULL OR i.category::text = CAST(:category AS text))
  AND (CAST(:frequency AS text) IS NULL OR i.purchase_frequency::text = CAST(:frequency AS text))
ORDER BY b.score DESC, i.canonical_name_en
LIMIT :limit
"""
)

_EXPLAIN_SQL = text("EXPLAIN " + _SEARCH_SQL.text)

# Focused probe: a pure alias trigram lookup. With seq scans disabled only the
# GIN(unaccent) index can serve this, so the plan deterministically proves the
# index backs fuzzy alias search regardless of table size.
_EXPLAIN_ALIAS_TRGM = text(
    "EXPLAIN SELECT ingredient_id FROM ingredient_aliases "
    "WHERE f_unaccent(lower(alias)) % f_unaccent(lower(:q))"
)


class SearchRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    def _params(
        self, q: str, category: str | None, frequency: str | None, limit: int
    ) -> dict[str, object]:
        return {
            "q": q,
            "org_id": self.org_id,
            "category": category,
            "frequency": frequency,
            "limit": limit,
        }

    async def search(
        self,
        *,
        q: str,
        category: str | None = None,
        frequency: str | None = None,
        limit: int = 20,
    ) -> list[Row[Any]]:
        result = await self.session.execute(
            _SEARCH_SQL, self._params(q, category, frequency, limit)
        )
        return list(result.all())

    async def explain(
        self, *, q: str, category: str | None = None, frequency: str | None = None, limit: int = 20
    ) -> str:
        result = await self.session.execute(
            _EXPLAIN_SQL, self._params(q, category, frequency, limit)
        )
        return "\n".join(row[0] for row in result.all())

    async def explain_alias_trigram(self, *, q: str) -> str:
        result = await self.session.execute(_EXPLAIN_ALIAS_TRGM, {"q": q})
        return "\n".join(row[0] for row in result.all())
