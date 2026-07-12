"""Bulk add-ingredient endpoint: POST /api/v1/ingredients/bulk."""

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


class _EnglishProvider:
    """English passthrough; Devanagari हल्दी → Turmeric. Confident detection."""

    name = "test"

    async def detect(self, text: str) -> DetectionResult:
        lang = "hi" if any("ऀ" <= c <= "ॿ" for c in text) else "en"
        return DetectionResult(lang=lang, confidence=0.95, candidates=[lang])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return "Turmeric" if text == "हल्दी" else text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return "haldi" if text == "हल्दी" else None


class _AmbiguousProvider:
    """Always low-confidence non-English, so a row without source_lang is ambiguous."""

    name = "amb"

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="es", confidence=0.4, candidates=["es", "en"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return None


async def _make_org(session: AsyncSession) -> None:
    session.add(Org(name="Hari Om"))
    await session.commit()


def _use(app, provider) -> None:
    app.dependency_overrides[get_translation_service] = lambda: TranslationService(provider)


BASE = {"category": "spice", "default_unit": "kg", "purchase_frequency": "monthly"}


@pytest.mark.asyncio
async def test_bulk_creates_multiple(db_session: AsyncSession, app, client: AsyncClient) -> None:
    await _make_org(db_session)
    _use(app, _EnglishProvider())

    resp = await client.post(
        "/api/v1/ingredients/bulk",
        json={
            "items": [
                {"display_name": "Basmati Rice", "source_lang": "en", **BASE},
                {"display_name": "Toor Dal", "source_lang": "en", **BASE},
                {"display_name": "हल्दी", "source_lang": "hi", **BASE},
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] == 3
    assert body["failed"] == 0
    assert all(r["ok"] and r["id"] for r in body["results"])
    # The Hindi row was translated to its English canonical.
    assert body["results"][2]["canonical_name_en"] == "Turmeric"

    listing = await client.get("/api/v1/ingredients")
    assert len(listing.json()) == 3


@pytest.mark.asyncio
async def test_bulk_partial_failure_isolated(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    await _make_org(db_session)
    _use(app, _AmbiguousProvider())

    resp = await client.post(
        "/api/v1/ingredients/bulk",
        json={
            "items": [
                {"display_name": "Rice", "source_lang": "en", **BASE},  # ok (lang given)
                {"display_name": "cilantro", **BASE},  # no lang -> ambiguous -> fails
                {"display_name": "Salt", "source_lang": "en", **BASE},  # ok
            ]
        },
    )
    assert resp.status_code == 207, resp.text
    body = resp.json()
    assert body["created"] == 2
    assert body["failed"] == 1
    assert body["results"][0]["ok"] is True
    assert body["results"][1]["ok"] is False
    assert "language" in body["results"][1]["error"].lower()
    assert body["results"][2]["ok"] is True

    # The two good rows persisted despite the middle failure (savepoint isolation).
    listing = await client.get("/api/v1/ingredients")
    assert {i["canonical_name_en"] for i in listing.json()} == {"Rice", "Salt"}


@pytest.mark.asyncio
async def test_bulk_rejects_empty(db_session: AsyncSession, app, client: AsyncClient) -> None:
    await _make_org(db_session)
    resp = await client.post("/api/v1/ingredients/bulk", json={"items": []})
    assert resp.status_code == 422
