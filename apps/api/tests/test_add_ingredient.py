"""Add-ingredient pipeline: translation, transliteration, synonyms, degradation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Org
from app.services.translation import (
    DetectionResult,
    TranslationService,
    get_translation_service,
)


class _MockProvider:
    """Translates हल्दी→Turmeric, romanizes →haldi, detects Devanagari as hi."""

    name = "mock"

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="hi", confidence=0.95, candidates=["hi"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return "Turmeric" if text == "हल्दी" else text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return "haldi" if text == "हल्दी" else None


class _FailingProvider:
    name = "failing"

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="hi", confidence=0.95, candidates=["hi"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        raise RuntimeError("provider down")

    async def romanize(self, text: str, *, source: str) -> str | None:
        raise RuntimeError("provider down")


class _AmbiguousProvider:
    name = "ambiguous"

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="es", confidence=0.5, candidates=["es", "en", "pt"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return None


async def _make_org(session: AsyncSession) -> None:
    session.add(Org(name="Hari Om"))
    await session.commit()


def _use_provider(app, provider) -> None:
    app.dependency_overrides[get_translation_service] = lambda: TranslationService(provider)


BASE = {"category": "spice", "default_unit": "kg", "purchase_frequency": "monthly"}


@pytest.mark.asyncio
async def test_add_haldi_translates_and_aliases(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _make_org(db_session)
    _use_provider(app, _MockProvider())

    resp = await client.post(
        "/api/v1/ingredients", json={"display_name": "हल्दी", "source_lang": "hi", **BASE}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["canonical_name_en"] == "Turmeric"
    assert body["needs_review"] is False
    aliases = {(a["alias"].lower(), a["lang"].lower()) for a in body["aliases"]}
    assert ("हल्दी", "hi") in aliases
    assert ("haldi", "hi-latn") in aliases
    assert ("turmeric", "en") in aliases


@pytest.mark.asyncio
async def test_provider_outage_still_saves_needs_review(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _make_org(db_session)
    _use_provider(app, _FailingProvider())

    resp = await client.post(
        "/api/v1/ingredients", json={"display_name": "हल्दी", "source_lang": "hi", **BASE}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Translation failed → canonical falls back to the input, flagged for review.
    assert body["canonical_name_en"] == "हल्दी"
    assert body["needs_review"] is True


@pytest.mark.asyncio
async def test_ambiguous_language_returns_422_with_candidates(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _make_org(db_session)
    _use_provider(app, _AmbiguousProvider())

    # No source_lang -> detection runs -> low-confidence non-English -> 422.
    resp = await client.post("/api/v1/ingredients", json={"display_name": "cilantro", **BASE})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["title"] == "Ambiguous language"


@pytest.mark.asyncio
async def test_english_ingredient_no_translation(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _make_org(db_session)
    _use_provider(app, _MockProvider())

    resp = await client.post(
        "/api/v1/ingredients", json={"display_name": "Cumin", "source_lang": "en", **BASE}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["canonical_name_en"] == "Cumin"
    # Curated synonyms still attach (jeera group).
    aliases = {a["alias"].lower() for a in body["aliases"]}
    assert "jeera" in aliases


@pytest.mark.asyncio
async def test_add_and_delete_user_alias(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _make_org(db_session)
    _use_provider(app, _MockProvider())
    created = (
        await client.post(
            "/api/v1/ingredients", json={"display_name": "Paneer", "source_lang": "en", **BASE}
        )
    ).json()
    ing_id = created["id"]

    resp = await client.post(
        f"/api/v1/ingredients/{ing_id}/aliases", json={"alias": "cottage cheese", "lang": "en"}
    )
    assert resp.status_code == 201, resp.text
    alias_id = resp.json()["id"]

    # Duplicate rejected.
    dup = await client.post(
        f"/api/v1/ingredients/{ing_id}/aliases", json={"alias": "cottage cheese", "lang": "en"}
    )
    assert dup.status_code == 409

    delete = await client.delete(f"/api/v1/ingredients/{ing_id}/aliases/{alias_id}")
    assert delete.status_code == 204
