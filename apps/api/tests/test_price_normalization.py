"""The STORED generated columns normalize unit price correctly in the database."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Category, DefaultUnit, PackUnit, PriceSource, StoreKind
from app.models.ingredient import Ingredient
from app.models.org import Org
from app.models.price import PriceEntry
from app.models.store import Store


async def _fixtures(session: AsyncSession) -> tuple[Org, Ingredient, Store]:
    org = Org(name="Test Org")
    session.add(org)
    await session.flush()
    ingredient = Ingredient(
        org_id=org.id,
        canonical_name_en="Basmati Rice",
        display_name="Basmati Rice",
        category=Category.STAPLE,
        default_unit=DefaultUnit.KG,
    )
    store = Store(org_id=org.id, name="CHEF'STORE", kind=StoreKind.CASH_AND_CARRY)
    session.add_all([ingredient, store])
    await session.flush()
    return org, ingredient, store


@pytest.mark.asyncio
async def test_per_kg_generated_from_lb(db_session: AsyncSession) -> None:
    org, ingredient, store = await _fixtures(db_session)
    entry = PriceEntry(
        org_id=org.id,
        ingredient_id=ingredient.id,
        store_id=store.id,
        pack_desc="20 lb bag",
        pack_qty=Decimal(20),
        pack_unit=PackUnit.LB,
        price_cents=5200,
        observed_at=dt.date(2026, 7, 1),
        source=PriceSource.INVOICE,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)

    assert entry.unit_price_cents_per_l is None
    assert entry.unit_price_cents_per_each is None
    # $52 / (20 * 0.45359237 kg) = 573.16 cents/kg
    assert round(float(entry.unit_price_cents_per_kg) / 100, 2) == 5.73


@pytest.mark.asyncio
async def test_per_l_and_per_each(db_session: AsyncSession) -> None:
    org, ingredient, store = await _fixtures(db_session)
    gallon = PriceEntry(
        org_id=org.id,
        ingredient_id=ingredient.id,
        store_id=store.id,
        pack_desc="1 gal jug",
        pack_qty=Decimal(1),
        pack_unit=PackUnit.GAL,
        price_cents=1000,
        observed_at=dt.date(2026, 7, 1),
        source=PriceSource.SHELF,
    )
    each = PriceEntry(
        org_id=org.id,
        ingredient_id=ingredient.id,
        store_id=store.id,
        pack_desc="tray of 30",
        pack_qty=Decimal(30),
        pack_unit=PackUnit.EACH,
        price_cents=600,
        observed_at=dt.date(2026, 7, 1),
        source=PriceSource.SHELF,
    )
    db_session.add_all([gallon, each])
    await db_session.flush()
    await db_session.refresh(gallon)
    await db_session.refresh(each)

    assert gallon.unit_price_cents_per_kg is None
    assert round(float(gallon.unit_price_cents_per_l) / 100, 2) == 2.64
    assert each.unit_price_cents_per_l is None
    assert float(each.unit_price_cents_per_each) == 20.0  # 600 / 30
