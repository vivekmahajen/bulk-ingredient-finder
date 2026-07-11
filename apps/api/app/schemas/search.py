"""Search response schemas."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.models.enums import Category, DefaultUnit, PurchaseFrequency


class BestPrice(BaseModel):
    """Cheapest current unit price for an ingredient, for actionable results."""

    price_cents: int
    unit_price_cents: float
    base_unit: str
    store_name: str
    observed_at: date


class SearchHit(BaseModel):
    id: uuid.UUID
    canonical_name_en: str
    display_name: str
    source_lang: str
    category: Category
    default_unit: DefaultUnit
    purchase_frequency: PurchaseFrequency
    needs_review: bool
    score: float
    matched_text: str
    matched_kind: str
    via_translation: bool = False
    best_price: BestPrice | None = None


class SearchResponse(BaseModel):
    query: str
    effective_query: str
    via_translation: bool
    results: list[SearchHit]
