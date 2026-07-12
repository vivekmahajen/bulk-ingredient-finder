"""Multilingual search: cross-language matching, filters, translation fallback, indexes."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    AliasKind,
    Category,
    DefaultUnit,
    PackUnit,
    PriceSource,
    PurchaseFrequency,
    StoreKind,
)
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.org import Org
from app.models.price import PriceEntry
from app.models.store import Store
from app.services.translation import DetectionResult, TranslationService, get_translation_service


async def _seed_org(session: AsyncSession) -> uuid.UUID:
    org = Org(name="Hari Om")
    session.add(org)
    await session.flush()
    return org.id


def _ingredient_with_aliases(
    org_id: uuid.UUID,
    canonical: str,
    category: Category,
    freq: PurchaseFrequency,
    aliases: list[tuple[str, str, AliasKind]],
) -> Ingredient:
    ing = Ingredient(
        org_id=org_id,
        canonical_name_en=canonical,
        display_name=canonical,
        category=category,
        default_unit=DefaultUnit.KG,
        purchase_frequency=freq,
        aliases=[
            IngredientAlias(org_id=org_id, alias=a, lang=lang, kind=kind)
            for a, lang, kind in aliases
        ],
    )
    return ing


@pytest.mark.asyncio
async def test_three_way_jeera(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session)
    db_session.add(
        _ingredient_with_aliases(
            org_id,
            "Cumin",
            Category.SPICE,
            PurchaseFrequency.MONTHLY,
            [
                ("जीरा", "hi", AliasKind.TRANSLATION),
                ("jeera", "hi-Latn", AliasKind.TRANSLITERATION),
                ("cumin", "en", AliasKind.TRANSLATION),
            ],
        )
    )
    await db_session.commit()

    for query in ["jeera", "जीरा", "cumin", "Cumin"]:
        resp = await client.get("/api/v1/search/ingredients", params={"q": query})
        assert resp.status_code == 200, resp.text
        names = [r["canonical_name_en"] for r in resp.json()["results"]]
        assert "Cumin" in names, f"{query!r} did not surface Cumin: {names}"


@pytest.mark.asyncio
async def test_fuzzy_and_filters(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session)
    db_session.add(
        _ingredient_with_aliases(
            org_id,
            "Turmeric",
            Category.SPICE,
            PurchaseFrequency.MONTHLY,
            [("haldi", "hi-Latn", AliasKind.SYNONYM)],
        )
    )
    db_session.add(
        _ingredient_with_aliases(
            org_id, "Paneer", Category.DAIRY, PurchaseFrequency.TWICE_WEEKLY, []
        )
    )
    await db_session.commit()

    # Fuzzy/typo tolerance via trigram.
    resp = await client.get("/api/v1/search/ingredients", params={"q": "turmreic"})
    assert "Turmeric" in [r["canonical_name_en"] for r in resp.json()["results"]]

    # Category filter excludes non-matching categories.
    resp = await client.get(
        "/api/v1/search/ingredients", params={"q": "paneer", "category": "spice"}
    )
    assert resp.json()["results"] == []
    resp = await client.get(
        "/api/v1/search/ingredients", params={"q": "paneer", "category": "dairy"}
    )
    assert [r["canonical_name_en"] for r in resp.json()["results"]] == ["Paneer"]


@pytest.mark.asyncio
async def test_best_price_attached(db_session: AsyncSession, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session)
    ing = _ingredient_with_aliases(
        org_id, "Basmati Rice", Category.STAPLE, PurchaseFrequency.MONTHLY, []
    )
    store = Store(org_id=org_id, name="CHEF'STORE Redding", kind=StoreKind.CASH_AND_CARRY)
    db_session.add_all([ing, store])
    await db_session.flush()
    db_session.add(
        PriceEntry(
            org_id=org_id,
            ingredient_id=ing.id,
            store_id=store.id,
            pack_desc="20 lb bag",
            pack_qty=Decimal(20),
            pack_unit=PackUnit.LB,
            price_cents=5200,
            observed_at=dt.date(2026, 7, 1),
            source=PriceSource.INVOICE,
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/search/ingredients", params={"q": "basmati"})
    hit = next(r for r in resp.json()["results"] if r["canonical_name_en"] == "Basmati Rice")
    assert hit["best_price"] is not None
    assert hit["best_price"]["store_name"] == "CHEF'STORE Redding"
    assert hit["best_price"]["base_unit"] == "kg"
    assert round(hit["best_price"]["unit_price_cents"] / 100, 2) == 5.73


class _EsProvider:
    """Detects Spanish, translates cúrcuma→turmeric."""

    name = "es"

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="es", confidence=0.95, candidates=["es"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return "turmeric" if "curcuma" in text.lower() or "cúrcuma" in text.lower() else text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return None


@pytest.mark.asyncio
async def test_translation_fallback(db_session: AsyncSession, app, client: AsyncClient) -> None:
    org_id = await _seed_org(db_session)
    db_session.add(
        _ingredient_with_aliases(org_id, "Turmeric", Category.SPICE, PurchaseFrequency.MONTHLY, [])
    )
    await db_session.commit()
    app.dependency_overrides[get_translation_service] = lambda: TranslationService(_EsProvider())

    # "cúrcuma" has no direct match → translate to "turmeric" → hit, flagged via_translation.
    resp = await client.get("/api/v1/search/ingredients", params={"q": "cúrcuma", "lang": "es"})
    body = resp.json()
    assert body["via_translation"] is True
    assert body["effective_query"] == "turmeric"
    assert [r["canonical_name_en"] for r in body["results"]] == ["Turmeric"]
    assert all(r["via_translation"] for r in body["results"])


@pytest.mark.asyncio
async def test_alias_search_uses_gin_index_not_seqscan(db_session: AsyncSession) -> None:
    org_id = await _seed_org(db_session)
    db_session.add(
        _ingredient_with_aliases(
            org_id,
            "Cumin",
            Category.SPICE,
            PurchaseFrequency.MONTHLY,
            [("jeera", "hi-Latn", AliasKind.TRANSLITERATION)],
        )
    )
    await db_session.commit()

    from app.repositories.search import SearchRepository

    repo = SearchRepository(db_session, org_id)
    await db_session.execute(text("SET LOCAL enable_seqscan = off"))

    # The full search query must never seq-scan the aliases table.
    full_plan = await repo.explain(q="jeera")
    assert "Seq Scan on ingredient_aliases" not in full_plan, full_plan

    # A focused alias fuzzy lookup is served by the GIN(unaccent) trigram index.
    trgm_plan = await repo.explain_alias_trigram(q="jeera")
    assert "ix_aliases_alias_trgm" in trgm_plan, trgm_plan
    assert "Seq Scan on ingredient_aliases" not in trgm_plan, trgm_plan
