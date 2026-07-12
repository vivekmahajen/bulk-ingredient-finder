"""Ingredient + alias Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AliasKind, Category, DefaultUnit, PurchaseFrequency


class IngredientAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alias: str
    lang: str
    kind: AliasKind


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
    created_at: datetime
    updated_at: datetime
    aliases: list[IngredientAliasRead] = []
