"""Price-entry Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PackUnit, PriceSource


class PriceEntryRead(BaseModel):
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
