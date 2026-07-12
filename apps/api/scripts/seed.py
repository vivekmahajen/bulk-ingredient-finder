"""Database seed (`make seed`).

Idempotent: bootstraps the single "Hari Om" dogfood org, an owner user, the 29
starter ingredients, and the 6 starter stores. Safe to run repeatedly — rows are
matched on natural keys (org name, user email, ingredient canonical name, store
name) and only inserted when missing.

Lives under ``scripts/`` (outside ``app/``) so its direct ``select(...)`` usage is
exempt from the repository-layer org-scoping lint test. ``run_seed`` takes a
session so it can run against the test database.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seed_data
from app.core.logging import configure_logging, get_logger
from app.db.session import async_session_factory, engine
from app.models.enums import Role
from app.models.ingredient import Ingredient
from app.models.org import Org
from app.models.store import Store
from app.models.user import User


async def run_seed(session: AsyncSession) -> dict[str, int]:
    """Insert any missing seed rows. Flushes but does not commit."""
    created = {"org": 0, "user": 0, "ingredients": 0, "stores": 0}

    org = (
        await session.execute(select(Org).where(Org.name == seed_data.ORG_NAME))
    ).scalar_one_or_none()
    if org is None:
        org = Org(name=seed_data.ORG_NAME)
        session.add(org)
        await session.flush()
        created["org"] += 1

    user = (
        await session.execute(select(User).where(User.email == seed_data.SEED_USER_EMAIL))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            org_id=org.id,
            email=seed_data.SEED_USER_EMAIL,
            display_name=seed_data.SEED_USER_NAME,
            role=Role.OWNER,
            locale="en",
        )
        session.add(user)
        await session.flush()
        created["user"] += 1

    existing_names = set(
        (
            await session.execute(
                select(Ingredient.canonical_name_en).where(Ingredient.org_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    for canonical, display, category, unit, freq in seed_data.INGREDIENTS:
        if canonical in existing_names:
            continue
        session.add(
            Ingredient(
                org_id=org.id,
                canonical_name_en=canonical,
                display_name=display,
                source_lang="en",
                category=category,
                default_unit=unit,
                purchase_frequency=freq,
                created_by=user.id,
            )
        )
        created["ingredients"] += 1

    existing_stores = set(
        (await session.execute(select(Store.name).where(Store.org_id == org.id))).scalars().all()
    )
    for name, kind, website, address, city, state, postal in seed_data.STORES:
        if name in existing_stores:
            continue
        session.add(
            Store(
                org_id=org.id,
                name=name,
                kind=kind,
                website=website,
                address_line=address,
                city=city,
                state=state,
                postal=postal,
            )
        )
        created["stores"] += 1

    await session.flush()
    return created


DEMO_ORG_NAME = "Demo Kitchen"


async def run_demo_seed(session: AsyncSession) -> dict[str, int]:
    """Seed a self-contained demo org with prices, for screenshots (idempotent)."""
    import datetime as _dt
    from decimal import Decimal

    from app.models.enums import DefaultUnit, PackUnit, PriceSource
    from app.models.price import PriceEntry

    org = (await session.execute(select(Org).where(Org.name == DEMO_ORG_NAME))).scalar_one_or_none()
    if org is not None:
        return {"demo_org": 0}
    org = Org(name=DEMO_ORG_NAME, home_lat=40.5865, home_lng=-122.3917)  # Redding, CA
    session.add(org)
    await session.flush()

    ingredients = [
        Ingredient(
            org_id=org.id,
            canonical_name_en=canonical,
            display_name=display,
            source_lang="en",
            category=category,
            default_unit=DefaultUnit.KG,
            purchase_frequency=freq,
        )
        for canonical, display, category, freq in [
            (
                "Basmati Rice",
                "Basmati Rice",
                seed_data.Category.STAPLE,
                seed_data.PurchaseFrequency.MONTHLY,
            ),
            (
                "Turmeric Powder",
                "Haldi",
                seed_data.Category.SPICE,
                seed_data.PurchaseFrequency.MONTHLY,
            ),
            (
                "Paneer",
                "Paneer",
                seed_data.Category.DAIRY,
                seed_data.PurchaseFrequency.TWICE_WEEKLY,
            ),
        ]
    ]
    stores = [
        Store(
            org_id=org.id,
            name="CHEF'STORE Redding",
            kind=seed_data.StoreKind.CASH_AND_CARRY,
            lat=40.5865,
            lng=-122.3917,
        ),
        Store(
            org_id=org.id,
            name="Raja Foods",
            kind=seed_data.StoreKind.ETHNIC_WHOLESALE,
            delivers=True,
            delivery_days=["Tue", "Fri"],
        ),
    ]
    session.add_all([*ingredients, *stores])
    await session.flush()

    prices = [
        (0, 0, "20 lb bag", 20, PackUnit.LB, 5200),
        (0, 1, "25 lb bag", 25, PackUnit.LB, 6800),
        (1, 0, "5 lb bag", 5, PackUnit.LB, 2400),
        (2, 0, "2 kg tub", 2, PackUnit.KG, 1600),
    ]
    for ing_i, store_i, desc, qty, unit, cents in prices:
        session.add(
            PriceEntry(
                org_id=org.id,
                ingredient_id=ingredients[ing_i].id,
                store_id=stores[store_i].id,
                pack_desc=desc,
                pack_qty=Decimal(qty),
                pack_unit=unit,
                price_cents=cents,
                observed_at=_dt.date(2026, 7, 5),
                source=PriceSource.INVOICE,
            )
        )
    return {"demo_org": 1}


async def seed(demo: bool = False) -> None:
    configure_logging()
    logger = get_logger("seed")
    async with async_session_factory() as session:
        created = await run_seed(session)
        if demo:
            created.update(await run_demo_seed(session))
        await session.commit()
    await engine.dispose()
    logger.info("seed_complete", **created)


if __name__ == "__main__":
    import sys

    asyncio.run(seed(demo="--demo" in sys.argv))
