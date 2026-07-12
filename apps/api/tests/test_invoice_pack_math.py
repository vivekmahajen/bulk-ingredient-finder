"""Invoice pack-math: per-pack price + $/base preview, all via app.units."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import PackUnit
from app.models.invoice import InvoiceLine
from app.services.invoice_pipeline import base_price_preview, per_unit_price_cents
from app.units import unit_price_cents_per_base


def _line(**kw: object) -> InvoiceLine:
    defaults: dict[str, object] = {
        "line_no": 1,
        "raw_text": "x",
        "confidence": 0.9,
        "is_credit": False,
    }
    defaults.update(kw)
    return InvoiceLine(**defaults)


def test_golden_6_of_number10_case_to_per_kg() -> None:
    # A case of six #10 cans (2.84 kg each) at $27.00/case -> $4.50/can.
    line = _line(case_count=6, pack_qty=2.84, pack_unit=PackUnit.KG, unit_price_cents=2700,
                 extended_cents=5400)
    assert per_unit_price_cents(line) == 450
    value, base = base_price_preview(line)
    assert base == "kg"
    assert value is not None and round(value, 1) == round(450 / 2.84, 1)  # ~158.5 c/kg


def test_golden_4x5lb_case_to_per_kg() -> None:
    line = _line(case_count=4, pack_qty=5, pack_unit=PackUnit.LB, unit_price_cents=1800,
                 extended_cents=7200)
    assert per_unit_price_cents(line) == 450  # 1800 / 4
    value, base = base_price_preview(line)
    assert base == "kg"
    # 450 cents / (5 lb -> 2.2679619 kg)
    assert value is not None and round(value, 2) == round(450 / (5 * 0.45359237), 2)


def test_golden_catch_weight_uses_line_total() -> None:
    # 40.2 lb of chicken at $1.89/lb -> line total $75.98 for one 40.2 lb pack.
    line = _line(case_count=None, pack_qty=40.2, pack_unit=PackUnit.LB, unit_price_cents=189,
                 extended_cents=7598)
    assert per_unit_price_cents(line) == 7598
    value, base = base_price_preview(line)
    assert base == "kg"
    # ~$1.89/lb == ~$4.17/kg == ~416.6 c/kg
    assert value is not None and 410 <= value <= 420


def test_golden_single_bag_no_case_division() -> None:
    line = _line(case_count=1, pack_qty=25, pack_unit=PackUnit.KG, unit_price_cents=3200,
                 extended_cents=3200)
    assert per_unit_price_cents(line) == 3200
    value, base = base_price_preview(line)
    assert base == "kg" and value is not None and round(value) == 128  # 3200/25


def test_missing_fields_yield_no_preview() -> None:
    assert base_price_preview(_line(pack_qty=None, pack_unit=None)) == (None, None)


@given(
    case_count=st.integers(min_value=2, max_value=24),
    per_case_cents=st.integers(min_value=100, max_value=500000),
    pack_qty=st.floats(min_value=0.05, max_value=50, allow_nan=False, allow_infinity=False),
    unit=st.sampled_from([PackUnit.KG, PackUnit.G, PackUnit.LB, PackUnit.OZ]),
)
def test_property_case_division_matches_units(
    case_count: int, per_case_cents: int, pack_qty: float, unit: PackUnit
) -> None:
    line = _line(
        case_count=case_count,
        pack_qty=pack_qty,
        pack_unit=unit,
        unit_price_cents=per_case_cents,
        extended_cents=per_case_cents * 3,
    )
    per_pack = per_unit_price_cents(line)
    assert per_pack == round(per_case_cents / case_count)
    value, _ = base_price_preview(line)
    expected = float(
        unit_price_cents_per_base(
            price_cents=per_pack, pack_qty=Decimal(str(pack_qty)), pack_unit=unit
        )
    )
    assert value == pytest.approx(expected, rel=1e-6)
