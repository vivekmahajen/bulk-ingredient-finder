"""Price-entry Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PackUnit, PriceSource

STALE_AFTER_DAYS = 45


class PriceCreate(BaseModel):
    ingredient_id: uuid.UUID
    store_id: uuid.UUID
    brand: str | None = None
    pack_desc: str = Field(min_length=1, max_length=200)
    pack_qty: float = Field(gt=0)
    pack_unit: PackUnit
    price_cents: int = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    observed_at: date | None = None
    source: PriceSource
    photo_url: str | None = None


class BulkPriceCreate(BaseModel):
    entries: list[PriceCreate] = Field(min_length=1, max_length=200)


class PriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    store_id: uuid.UUID
    brand: str | None
    pack_desc: str
    pack_qty: float
    pack_unit: PackUnit
    price_cents: int
    currency: str
    observed_at: date
    source: PriceSource
    photo_url: str | None
    created_at: datetime
    unit_price_cents_per_kg: float | None
    unit_price_cents_per_l: float | None
    unit_price_cents_per_each: float | None
    # Derived, relative to "today":
    unit_price_cents: float | None
    base_unit: str
    age_days: int
    stale: bool
    warnings: list[str] = []


class BulkRowResult(BaseModel):
    index: int
    ok: bool
    id: uuid.UUID | None = None
    warnings: list[str] = []
    error: str | None = None


class BulkResult(BaseModel):
    created: int
    failed: int
    results: list[BulkRowResult]


class PaginatedPrices(BaseModel):
    items: list[PriceRead]
    total: int
    limit: int
    offset: int


class PriceHistoryPoint(BaseModel):
    observed_at: date
    price_cents: int
    pack_desc: str
    unit_price_cents: float | None
    base_unit: str
    source: PriceSource
    age_days: int
    stale: bool


class StoreSeries(BaseModel):
    store_id: uuid.UUID
    store_name: str
    points: list[PriceHistoryPoint]


class PriceHistory(BaseModel):
    ingredient_id: uuid.UUID
    series: list[StoreSeries]
