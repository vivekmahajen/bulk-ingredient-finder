"""Search orchestration: normalize → candidate search → translation fallback."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import RequestContext
from app.repositories.search import SearchRepository
from app.schemas.search import BestPrice, SearchHit, SearchResponse
from app.services.translation import TranslationService


def _to_hit(row: Row[Any], *, via_translation: bool) -> SearchHit:
    best_price = None
    if row.unit_price_cents is not None:
        best_price = BestPrice(
            price_cents=row.price_cents,
            unit_price_cents=float(row.unit_price_cents),
            base_unit=row.base_unit,
            store_name=row.store_name,
            observed_at=row.observed_at,
        )
    return SearchHit(
        id=row.id,
        canonical_name_en=row.canonical_name_en,
        display_name=row.display_name,
        source_lang=row.source_lang,
        category=row.category,
        default_unit=row.default_unit,
        purchase_frequency=row.purchase_frequency,
        needs_review=row.needs_review,
        score=float(row.score),
        matched_text=row.matched_text,
        matched_kind=row.matched_kind,
        via_translation=via_translation,
        best_price=best_price,
    )


async def search_ingredients(
    session: AsyncSession,
    ctx: RequestContext,
    *,
    q: str,
    lang: str | None = None,
    category: str | None = None,
    frequency: str | None = None,
    limit: int = 20,
    translation: TranslationService,
) -> SearchResponse:
    q = q.strip()
    repo = SearchRepository(session, ctx.org_id)

    rows = await repo.search(q=q, category=category, frequency=frequency, limit=limit)
    if rows:
        return SearchResponse(
            query=q,
            effective_query=q,
            via_translation=False,
            results=[_to_hit(r, via_translation=False) for r in rows],
        )

    # Zero hits: if the query language isn't English, translate and retry once.
    detected = lang
    if not detected:
        detection = await translation.detect(q)
        detected = detection.lang
    if detected and detected.split("-")[0] != "en":
        outcome = await translation.to_english(display_name=q, source_lang=detected)
        english_q = outcome.canonical_en
        if english_q.strip().lower() != q.lower():
            rows = await repo.search(
                q=english_q, category=category, frequency=frequency, limit=limit
            )
            if rows:
                return SearchResponse(
                    query=q,
                    effective_query=english_q,
                    via_translation=True,
                    results=[_to_hit(r, via_translation=True) for r in rows],
                )

    return SearchResponse(query=q, effective_query=q, via_translation=False, results=[])
