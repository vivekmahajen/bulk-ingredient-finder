"""Price-entry helpers: unit/category warnings, normalization, serialization."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import Category, PackUnit
from app.models.price import PriceEntry
from app.schemas.price import STALE_AFTER_DAYS, PriceRead
from app.units import Dimension, base_unit_of, dimension_of, unit_price_cents_per_base

# Categories whose packs are almost always sold by mass; a volume unit is suspect.
_MASS_CATEGORIES = {Category.PROTEIN, Category.PRODUCE, Category.STAPLE, Category.SPICE}
# Categories almost always sold by volume; a mass unit is suspect.
_VOLUME_CATEGORIES = {Category.BEVERAGE}


def unit_category_warnings(category: Category, pack_unit: PackUnit) -> list[str]:
    """Non-fatal sanity checks (e.g. 'liters of chicken'). Warnings, never errors."""
    warnings: list[str] = []
    dim = dimension_of(pack_unit)
    if category in _MASS_CATEGORIES and dim == Dimension.VOLUME:
        warnings.append(
            f"{pack_unit.value} is a volume unit but {category.value} is usually sold by weight — "
            "double-check the pack."
        )
    if category in _VOLUME_CATEGORIES and dim == Dimension.MASS:
        warnings.append(
            f"{pack_unit.value} is a weight unit but {category.value} is usually sold by volume — "
            "double-check the pack."
        )
    return warnings


def age_days(observed_at: date, today: date) -> int:
    return max(0, (today - observed_at).days)


def to_read(entry: PriceEntry, *, today: date, warnings: list[str] | None = None) -> PriceRead:
    """Serialize a persisted entry, computing normalized price + staleness."""
    unit_price = unit_price_cents_per_base(
        price_cents=entry.price_cents,
        pack_qty=Decimal(str(entry.pack_qty)),
        pack_unit=entry.pack_unit,
    )
    days = age_days(entry.observed_at, today)
    return PriceRead(
        id=entry.id,
        ingredient_id=entry.ingredient_id,
        store_id=entry.store_id,
        brand=entry.brand,
        pack_desc=entry.pack_desc,
        pack_qty=float(entry.pack_qty),
        pack_unit=entry.pack_unit,
        price_cents=entry.price_cents,
        currency=entry.currency,
        observed_at=entry.observed_at,
        source=entry.source,
        photo_url=entry.photo_url,
        created_at=entry.created_at,
        unit_price_cents_per_kg=(
            float(entry.unit_price_cents_per_kg)
            if entry.unit_price_cents_per_kg is not None
            else None
        ),
        unit_price_cents_per_l=(
            float(entry.unit_price_cents_per_l)
            if entry.unit_price_cents_per_l is not None
            else None
        ),
        unit_price_cents_per_each=(
            float(entry.unit_price_cents_per_each)
            if entry.unit_price_cents_per_each is not None
            else None
        ),
        unit_price_cents=float(unit_price),
        base_unit=base_unit_of(entry.pack_unit),
        age_days=days,
        stale=days > STALE_AFTER_DAYS,
        warnings=warnings or [],
    )
