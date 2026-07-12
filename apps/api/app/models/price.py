"""PriceEntry model, with normalized unit-price generated columns.

``unit_price_cents_per_kg`` / ``_per_l`` / ``_per_each`` are STORED generated
columns: for any row exactly one is non-null, depending on the pack unit's
dimension (mass / volume / count). This lets search rank by a normalized price
without recomputing conversions per query. The conversion factors mirror
``app/units.py`` and ``packages/shared/src/units.ts``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, OrgScopedMixin, UUIDPrimaryKeyMixin
from app.models._sa_enum import pg_enum
from app.models.enums import PackUnit, PriceSource

# Compare the enum column directly (not via ``::text``) so the expression is
# IMMUTABLE, as Postgres requires for a generated column. Mirrors migration 0002.
_PER_KG = """
CASE
  WHEN pack_unit = 'kg' THEN price_cents / (pack_qty * 1)
  WHEN pack_unit = 'g'  THEN price_cents / (pack_qty * 0.001)
  WHEN pack_unit = 'lb' THEN price_cents / (pack_qty * 0.45359237)
  WHEN pack_unit = 'oz' THEN price_cents / (pack_qty * 0.028349523)
  ELSE NULL
END
"""

_PER_L = """
CASE
  WHEN pack_unit = 'l'   THEN price_cents / (pack_qty * 1)
  WHEN pack_unit = 'ml'  THEN price_cents / (pack_qty * 0.001)
  WHEN pack_unit = 'gal' THEN price_cents / (pack_qty * 3.785411784)
  ELSE NULL
END
"""

_PER_EACH = """
CASE WHEN pack_unit = 'each' THEN price_cents / pack_qty ELSE NULL END
"""


class PriceEntry(UUIDPrimaryKeyMixin, OrgScopedMixin, Base):
    __tablename__ = "price_entries"

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand: Mapped[str | None] = mapped_column(Text, nullable=True)
    pack_desc: Mapped[str] = mapped_column(Text, nullable=False)
    pack_qty: Mapped[float] = mapped_column(Numeric, nullable=False)
    pack_unit: Mapped[PackUnit] = mapped_column(pg_enum(PackUnit, "pack_unit"), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="USD", server_default="USD"
    )
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[PriceSource] = mapped_column(
        pg_enum(PriceSource, "price_source"), nullable=False
    )
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    unit_price_cents_per_kg: Mapped[float | None] = mapped_column(
        Numeric, Computed(_PER_KG, persisted=True), nullable=True
    )
    unit_price_cents_per_l: Mapped[float | None] = mapped_column(
        Numeric, Computed(_PER_L, persisted=True), nullable=True
    )
    unit_price_cents_per_each: Mapped[float | None] = mapped_column(
        Numeric, Computed(_PER_EACH, persisted=True), nullable=True
    )
