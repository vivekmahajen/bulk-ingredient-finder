"""Compare / answer-screen schemas."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field


class StoreOption(BaseModel):
    store_id: uuid.UUID
    store_name: str
    store_kind: str | None = None
    brand: str | None = None
    unit_price_cents: float
    base_unit: str
    pack_desc: str
    price_cents: int
    observed_at: date
    age_days: int
    distance_km: float | None
    delivers: bool
    confidence: str  # high | medium | low
    savings_vs_worst_pct: float


class IngredientCompare(BaseModel):
    ingredient_id: uuid.UUID
    canonical_name_en: str
    base_unit: str
    best_store_id: uuid.UUID | None
    options: list[StoreOption]


class BasketStoreTotal(BaseModel):
    store_id: uuid.UUID
    store_name: str
    total_cents: int
    covers: int  # how many of the requested ingredients this store prices


class SplitSuggestion(BaseModel):
    primary: BasketStoreTotal
    secondary: BasketStoreTotal | None
    total_cents: int
    savings_vs_single_cents: int


class BasketSummary(BaseModel):
    single_store: BasketStoreTotal | None
    best_per_item_total_cents: int
    split: SplitSuggestion | None
    savings_best_vs_single_cents: int


class CompareResponse(BaseModel):
    ingredients: list[IngredientCompare]
    basket_summary: BasketSummary | None
    radius_km: float | None
    include_delivery: bool
    store_count: int
    notes: list[str] = []


class QuantityCompareRequest(BaseModel):
    ingredient_ids: list[uuid.UUID] = Field(min_length=1)
    radius_km: float | None = Field(default=None, ge=0)
    include_delivery: bool = True
    quantities: dict[uuid.UUID, float] = {}
