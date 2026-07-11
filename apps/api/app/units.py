"""Unit conversion + price normalization.

Mirrors ``packages/shared/src/units.ts`` — keep the factor tables in sync.

Every purchasable pack is normalized to a price per **base unit**, where the base
unit depends on the pack's physical dimension:

  * mass   -> price per kilogram   (kg)
  * volume -> price per liter      (l)
  * count  -> price per each       (each)

Canonical conversion factors (exact, from the spec):
  lb -> kg : 0.45359237
  oz -> g  : 28.349523      (=> oz -> kg : 0.028349523)
  gal -> l : 3.785411784
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

# Exact conversion factors as Decimal to avoid binary float drift.
LB_TO_KG = Decimal("0.45359237")
OZ_TO_G = Decimal("28.349523")
GAL_TO_L = Decimal("3.785411784")


class Dimension(StrEnum):
    MASS = "mass"
    VOLUME = "volume"
    COUNT = "count"


class PackUnit(StrEnum):
    KG = "kg"
    G = "g"
    LB = "lb"
    OZ = "oz"
    L = "l"
    ML = "ml"
    GAL = "gal"
    EACH = "each"


# Base unit per dimension.
BASE_UNIT: dict[Dimension, str] = {
    Dimension.MASS: "kg",
    Dimension.VOLUME: "l",
    Dimension.COUNT: "each",
}

# Which dimension each pack unit belongs to.
UNIT_DIMENSION: dict[PackUnit, Dimension] = {
    PackUnit.KG: Dimension.MASS,
    PackUnit.G: Dimension.MASS,
    PackUnit.LB: Dimension.MASS,
    PackUnit.OZ: Dimension.MASS,
    PackUnit.L: Dimension.VOLUME,
    PackUnit.ML: Dimension.VOLUME,
    PackUnit.GAL: Dimension.VOLUME,
    PackUnit.EACH: Dimension.COUNT,
}

# Multiply a quantity in the given unit by this factor to get the base unit.
TO_BASE_FACTOR: dict[PackUnit, Decimal] = {
    PackUnit.KG: Decimal(1),
    PackUnit.G: Decimal("0.001"),
    PackUnit.LB: LB_TO_KG,
    PackUnit.OZ: OZ_TO_G / Decimal(1000),  # oz -> g -> kg
    PackUnit.L: Decimal(1),
    PackUnit.ML: Decimal("0.001"),
    PackUnit.GAL: GAL_TO_L,
    PackUnit.EACH: Decimal(1),
}


def dimension_of(unit: PackUnit | str) -> Dimension:
    return UNIT_DIMENSION[PackUnit(unit)]


def base_unit_of(unit: PackUnit | str) -> str:
    return BASE_UNIT[dimension_of(unit)]


def to_base_quantity(qty: Decimal, unit: PackUnit | str) -> Decimal:
    """Convert ``qty`` in ``unit`` to its base-unit quantity (kg / l / each)."""
    return Decimal(qty) * TO_BASE_FACTOR[PackUnit(unit)]


def from_base_quantity(qty_base: Decimal, unit: PackUnit | str) -> Decimal:
    """Inverse of :func:`to_base_quantity` — base-unit quantity back to ``unit``."""
    return Decimal(qty_base) / TO_BASE_FACTOR[PackUnit(unit)]


def unit_price_cents_per_base(
    *, price_cents: int, pack_qty: Decimal, pack_unit: PackUnit | str
) -> Decimal:
    """Normalized price: cents per base unit for the pack's dimension.

    ``price_cents`` buys ``pack_qty`` × ``pack_unit``; return cents per kg / l / each.
    """
    base_qty = to_base_quantity(Decimal(pack_qty), pack_unit)
    if base_qty == 0:
        raise ValueError("pack_qty must be non-zero")
    return Decimal(price_cents) / base_qty
