"""Store Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import StoreKind


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
