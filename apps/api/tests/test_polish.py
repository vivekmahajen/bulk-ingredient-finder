"""PR-8: translation cache hit, locale persistence, registration gating."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Org
from app.models.translation_cache import TranslationCache
from app.models.user import User
from app.services.translation import (
    DetectionResult,
    TranslationService,
    get_translation_service,
)

BASE = {"category": "spice", "default_unit": "kg", "purchase_frequency": "monthly"}


class _CountingProvider:
    """Counts translate calls so we can prove the cache prevents a second hit."""

    name = "counting"

    def __init__(self) -> None:
        self.translate_calls = 0

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="hi", confidence=0.95, candidates=["hi"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        self.translate_calls += 1
        return "Turmeric"

    async def romanize(self, text: str, *, source: str) -> str | None:
        return "haldi"


@pytest.mark.asyncio
async def test_translation_cache_hit(db_session: AsyncSession, app, client: AsyncClient) -> None:
    session = db_session
    session.add(Org(name="Hari Om"))
    await session.commit()
    provider = _CountingProvider()
    app.dependency_overrides[get_translation_service] = lambda: TranslationService(provider)

    payload = {"display_name": "हल्दी", "source_lang": "hi", **BASE}
    first = await client.post("/api/v1/ingredients", json=payload)
    second = await client.post("/api/v1/ingredients", json=payload)
    assert first.status_code == 201 and second.status_code == 201

    # Provider hit once; the second add served from translation_cache.
    assert provider.translate_calls == 1
    cache_rows = await db_session.scalar(select(func.count()).select_from(TranslationCache))
    assert cache_rows == 1


@pytest.mark.asyncio
async def test_locale_persists_to_user(db_session: AsyncSession, client: AsyncClient) -> None:
    org = Org(name="Hari Om")
    db_session.add(org)
    await db_session.flush()
    db_session.add(User(org_id=org.id, email="o@x.example", display_name="Owner", locale="en"))
    await db_session.commit()

    me = (await client.get("/api/v1/me")).json()
    assert me["locale"] == "en"

    updated = await client.patch("/api/v1/me/locale", json={"locale": "hi"})
    assert updated.status_code == 200
    assert updated.json()["locale"] == "hi"
    # Persisted.
    assert (await client.get("/api/v1/me")).json()["locale"] == "hi"

    # Unsupported locale rejected.
    assert (await client.patch("/api/v1/me/locale", json={"locale": "xx"})).status_code == 422


@pytest.mark.asyncio
async def test_registration_disabled_in_dogfood(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    # MULTI_TENANT defaults to false → self-registration is forbidden.
    resp = await client.post(
        "/api/v1/register",
        json={"org_name": "New Kitchen", "email": "new@x.example", "display_name": "New"},
    )
    assert resp.status_code == 403
