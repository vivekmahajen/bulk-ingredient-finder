"""Ingredient + alias Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AliasKind, Category, DefaultUnit, PurchaseFrequency


class IngredientAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alias: str
    lang: str
    kind: AliasKind


class IngredientForecastData(BaseModel):
    """Optional demand forecast + sourcing. Every field may be omitted — attach
    a few months, the full year, serving size, and/or the preferred vendor."""

    model_config = ConfigDict(from_attributes=True)

    jan: float | None = None
    feb: float | None = None
    mar: float | None = None
    apr: float | None = None
    may: float | None = None
    jun: float | None = None
    jul: float | None = None
    aug: float | None = None
    sep: float | None = None
    oct: float | None = None
    nov: float | None = None
    dec: float | None = None
    annual: float | None = None
    g_ml_per_serving: float | None = None
    recommended_vendor: str | None = Field(default=None, max_length=1000)
    vendor_website: str | None = Field(default=None, max_length=1000)


class IngredientCreate(BaseModel):
    """Payload for POST /ingredients.

    Only ``display_name`` is required; category / unit / frequency fall back to
    sensible defaults, and ``forecast`` (monthly demand + sourcing) is optional.
    ``source_lang`` omitted → language detection.
    """

    display_name: str = Field(min_length=1, max_length=200)
    source_lang: str | None = Field(default=None, max_length=10)
    category: Category = Category.OTHER
    default_unit: DefaultUnit = DefaultUnit.EACH
    purchase_frequency: PurchaseFrequency = PurchaseFrequency.WEEKLY
    par_level: float | None = Field(default=None, ge=0)
    notes: str | None = None
    forecast: IngredientForecastData | None = None


class BulkIngredientCreate(BaseModel):
    """Payload for POST /ingredients/bulk — up to 100 ingredients at once."""

    items: list[IngredientCreate] = Field(min_length=1, max_length=100)


class BulkIngredientRowResult(BaseModel):
    """Per-row outcome for a bulk add (207-style: some rows may fail)."""

    index: int
    ok: bool
    id: uuid.UUID | None = None
    canonical_name_en: str | None = None
    needs_review: bool = False
    error: str | None = None


class BulkIngredientResult(BaseModel):
    created: int
    failed: int
    results: list[BulkIngredientRowResult]


class AliasCreate(BaseModel):
    """Payload for POST /ingredients/{id}/aliases (user correction)."""

    alias: str = Field(min_length=1, max_length=200)
    lang: str = Field(min_length=2, max_length=10)


class IngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_name_en: str
    display_name: str
    source_lang: str
    category: Category
    default_unit: DefaultUnit
    purchase_frequency: PurchaseFrequency
    par_level: float | None
    notes: str | None
    is_active: bool
    needs_review: bool
    created_at: datetime
    updated_at: datetime
    aliases: list[IngredientAliasRead] = []
    forecast: IngredientForecastData | None = None
