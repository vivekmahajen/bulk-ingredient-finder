"""Property-based + golden tests for unit conversion and price normalization."""

from __future__ import annotations

import math
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.units import (
    PackUnit,
    base_unit_of,
    from_base_quantity,
    to_base_quantity,
    unit_price_cents_per_base,
)

_QTY = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)


@given(qty=_QTY, unit=st.sampled_from(list(PackUnit)))
def test_to_from_base_roundtrip(qty: Decimal, unit: PackUnit) -> None:
    """Converting to the base unit and back recovers the original quantity."""
    roundtrip = from_base_quantity(to_base_quantity(qty, unit), unit)
    assert math.isclose(float(roundtrip), float(qty), rel_tol=1e-9)


@given(
    price_cents=st.integers(min_value=1, max_value=10_000_000),
    qty=_QTY,
    unit=st.sampled_from(list(PackUnit)),
)
def test_unit_price_is_positive_and_scales(price_cents: int, qty: Decimal, unit: PackUnit) -> None:
    per_base = unit_price_cents_per_base(price_cents=price_cents, pack_qty=qty, pack_unit=unit)
    assert per_base > 0
    # Doubling the pack quantity halves the per-base price.
    per_base_double = unit_price_cents_per_base(
        price_cents=price_cents, pack_qty=qty * 2, pack_unit=unit
    )
    assert math.isclose(float(per_base_double), float(per_base) / 2, rel_tol=1e-9)


def test_base_unit_mapping() -> None:
    assert base_unit_of(PackUnit.LB) == "kg"
    assert base_unit_of(PackUnit.GAL) == "l"
    assert base_unit_of(PackUnit.EACH) == "each"


def test_golden_20lb_bag_at_52_dollars() -> None:
    """From the PR-6 spec: a 20 lb bag at $52 normalizes to ~$5.73/kg."""
    per_kg_cents = unit_price_cents_per_base(
        price_cents=5200, pack_qty=Decimal(20), pack_unit=PackUnit.LB
    )
    assert round(float(per_kg_cents) / 100, 2) == 5.73


def test_golden_gallon_conversion() -> None:
    """1 gallon at $10 -> $2.64/l (3.785411784 l per gallon)."""
    per_l_cents = unit_price_cents_per_base(
        price_cents=1000, pack_qty=Decimal(1), pack_unit=PackUnit.GAL
    )
    assert round(float(per_l_cents) / 100, 2) == 2.64
