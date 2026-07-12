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


class IngredientCreate(BaseModel):
    """Payload for POST /ingredients. ``source_lang`` is optional → detection."""

    display_name: str = Field(min_length=1, max_length=200)
    source_lang: str | None = Field(default=None, max_length=10)
    category: Category
    default_unit: DefaultUnit
    purchase_frequency: PurchaseFrequency = PurchaseFrequency.WEEKLY
    par_level: float | None = Field(default=None, ge=0)
    notes: str | None = None


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
