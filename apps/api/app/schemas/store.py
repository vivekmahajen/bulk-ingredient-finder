"""Store + org Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PackUnit, PriceSource, StoreKind


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: StoreKind
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    postal: str | None = None
    lat: float | None = None
    lng: float | None = None
    website: str | None = None
    phone: str | None = None
    delivers: bool = False
    delivery_days: list[str] | None = None
    min_order: float | None = Field(default=None, ge=0)
    notes: str | None = None


class StoreUpdate(BaseModel):
    """All fields optional — partial update (PATCH)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: StoreKind | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    postal: str | None = None
    lat: float | None = None
    lng: float | None = None
    website: str | None = None
    phone: str | None = None
    delivers: bool | None = None
    delivery_days: list[str] | None = None
    min_order: float | None = Field(default=None, ge=0)
    notes: str | None = None


class StoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: StoreKind
    address_line: str | None
    city: str | None
    state: str | None
    postal: str | None
    lat: float | None
    lng: float | None
    website: str | None
    phone: str | None
    delivers: bool
    delivery_days: list[str] | None
    min_order: float | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    distance_km: float | None = None
    geocoded: bool = True


class StorePriceRow(BaseModel):
    ingredient_id: uuid.UUID
    canonical_name_en: str
    display_name: str
    price_cents: int
    pack_desc: str
    pack_qty: float
    pack_unit: PackUnit
    unit_price_cents: float | None
    base_unit: str
    observed_at: date
    source: PriceSource


class StoreWin(BaseModel):
    ingredient_id: uuid.UUID
    canonical_name_en: str
    unit_price_cents: float
    observed_at: date


class OrgRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    home_lat: float | None
    home_lng: float | None


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    home_address: str | None = None
    home_lat: float | None = None
    home_lng: float | None = None
