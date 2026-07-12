"""Invoice capture endpoints: upload → extract (NullExtractor) → review → commit."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1 import invoices as invoices_api
from app.db.session import get_session_factory
from app.deps import RequestContext, get_context
from app.models.enums import AliasKind, Category, DefaultUnit, StoreKind
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.org import Org
from app.models.price import PriceEntry
from app.models.store import Store
from app.services.image_prep import sniff_content_type
from app.services.invoice_extraction import NullInvoiceExtractor
from tests.fixtures.gen_invoices import produce_invoice, sha256, swad_invoice, thermal_invoice


class InMemoryStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.blobs[key] = data
        return key

    def get(self, key: str) -> bytes:
        return self.blobs[key]

    def signed_url(self, key: str, ttl: int = 3600) -> str | None:
        return None


async def _seed_ingredient(db_session, org_id, canonical, *, aliases=()):  # type: ignore[no-untyped-def]
    ing = Ingredient(
        org_id=org_id,
        canonical_name_en=canonical,
        display_name=canonical,
        source_lang="en",
        category=Category.OTHER,
        default_unit=DefaultUnit.KG,
    )
    db_session.add(ing)
    await db_session.flush()
    for alias in aliases:
        db_session.add(
            IngredientAlias(
                org_id=org_id, ingredient_id=ing.id, alias=alias, lang="hi", kind=AliasKind.SYNONYM
            )
        )
    return ing


@pytest_asyncio.fixture()
async def env(db_session, db_engine, app):  # type: ignore[no-untyped-def]
    org = Org(name="Hari Om")
    db_session.add(org)
    await db_session.commit()

    mem = InMemoryStorage()
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)
    app.dependency_overrides[get_context] = lambda: RequestContext(org.id, None)
    app.dependency_overrides[invoices_api.get_storage] = lambda: mem
    app.dependency_overrides[get_session_factory] = lambda: factory
    return SimpleNamespace(org=org, mem=mem)


def _use_extractor(app, fixtures: dict[str, dict]) -> None:
    app.dependency_overrides[invoices_api.get_extractor] = lambda: NullInvoiceExtractor(fixtures)


async def _upload(client: AsyncClient, image: bytes, name: str = "inv.jpg"):  # type: ignore[no-untyped-def]
    return await client.post(
        "/api/v1/invoices", files={"file": (name, image, "image/jpeg")}
    )


@pytest.mark.asyncio
async def test_swad_flow_extract_review_commit(env, app, client, db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed_ingredient(db_session, env.org.id, "basmati rice")
    await _seed_ingredient(db_session, env.org.id, "canned tomatoes")
    await _seed_ingredient(db_session, env.org.id, "cumin", aliases=["jeera"])
    await db_session.commit()

    image, golden = swad_invoice()
    _use_extractor(app, {sha256(image): golden})

    resp = await _upload(client, image)
    assert resp.status_code == 201, resp.text
    invoice_id = resp.json()["id"]

    detail = (await client.get(f"/api/v1/invoices/{invoice_id}")).json()
    assert detail["status"] == "needs_review"
    assert len(detail["lines"]) == 3
    # The Devanagari raw text is preserved verbatim — the multilingual proof point.
    assert any("बासमती" in ln["raw_text"] for ln in detail["lines"])
    # jeera → cumin matched via the seeded synonym.
    cumin_line = next(ln for ln in detail["lines"] if ln["description_en"] == "cumin seeds")
    assert cumin_line["match_status"] == "auto_matched"
    assert cumin_line["matched_ingredient_id"] is not None

    store = Store(org_id=env.org.id, name="SWAD Wholesale", kind=StoreKind.ETHNIC_WHOLESALE)
    db_session.add(store)
    await db_session.commit()

    commit = await client.post(
        f"/api/v1/invoices/{invoice_id}/commit", json={"store_id": str(store.id)}
    )
    assert commit.status_code == 200, commit.text
    body = commit.json()
    assert body["created"] == 3
    assert body["skipped_duplicates"] == 0
    assert body["totals_match"] is True  # 12800 + 5400 + 1800 == 20000

    # Prices created with invoice provenance and correct per-pack cents.
    rows = (
        await db_session.execute(
            select(PriceEntry).where(PriceEntry.org_id == env.org.id)
        )
    ).scalars().all()
    assert len(rows) == 3
    assert all(r.invoice_line_id is not None and r.source.value == "invoice" for r in rows)
    tomatoes = next(r for r in rows if float(r.pack_qty) == pytest.approx(2.84))
    assert tomatoes.price_cents == 450  # 2700 case / 6


@pytest.mark.asyncio
async def test_thermal_excludes_fee_and_credit(env, app, client, db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed_ingredient(db_session, env.org.id, "rice")
    await db_session.commit()
    image, golden = thermal_invoice()
    _use_extractor(app, {sha256(image): golden})

    resp = await _upload(client, image, name="thermal.jpg")
    invoice_id = resp.json()["id"]
    detail = (await client.get(f"/api/v1/invoices/{invoice_id}")).json()
    fee = next(ln for ln in detail["lines"] if ln["description_en"].startswith("FEE:"))
    assert fee["match_status"] == "excluded"

    store = Store(org_id=env.org.id, name="C&C", kind=StoreKind.CASH_AND_CARRY)
    db_session.add(store)
    await db_session.commit()
    body = (
        await client.post(
            f"/api/v1/invoices/{invoice_id}/commit", json={"store_id": str(store.id)}
        )
    ).json()
    # Only the rice line is a real product; FEE + credit are excluded.
    assert body["created"] == 1
    assert body["excluded"] == 2


@pytest.mark.asyncio
async def test_upload_hardening(env, app, client) -> None:  # type: ignore[no-untyped-def]
    _use_extractor(app, {})
    # Bad magic bytes -> 415.
    bad = await client.post(
        "/api/v1/invoices", files={"file": ("x.txt", b"this is not an image", "image/jpeg")}
    )
    assert bad.status_code == 415

    # sniffing recognizes real jpeg magic
    assert sniff_content_type(b"\xff\xd8\xff\x00") == "image/jpeg"


@pytest.mark.asyncio
async def test_upload_oversize_413(env, app, client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core import config

    monkeypatch.setattr(config.settings, "max_upload_mb", 1)
    _use_extractor(app, {})
    big = b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024)
    resp = await _upload(client, big)
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_dedupe_by_sha(env, app, client) -> None:  # type: ignore[no-untyped-def]
    image, golden = swad_invoice()
    _use_extractor(app, {sha256(image): golden})
    first = await _upload(client, image)
    assert first.status_code == 201
    second = await _upload(client, image)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_quota_429(env, app, client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core import config

    monkeypatch.setattr(config.settings, "extractions_per_day", 1)
    img_a, gold_a = swad_invoice()
    img_b, gold_b = produce_invoice()
    _use_extractor(app, {sha256(img_a): gold_a, sha256(img_b): gold_b})

    assert (await _upload(client, img_a, "a.jpg")).status_code == 201
    over = await _upload(client, img_b, "b.jpg")
    assert over.status_code == 429


@pytest.mark.asyncio
async def test_reject(env, app, client) -> None:  # type: ignore[no-untyped-def]
    image, golden = produce_invoice()
    _use_extractor(app, {sha256(image): golden})
    invoice_id = (await _upload(client, image)).json()["id"]
    resp = await client.post(f"/api/v1/invoices/{invoice_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_cross_org_invoice_404(env, app, client, db_session, db_engine) -> None:  # type: ignore[no-untyped-def]
    # Upload as env.org, then switch context to a different org -> 404.
    image, golden = produce_invoice()
    _use_extractor(app, {sha256(image): golden})
    invoice_id = (await _upload(client, image)).json()["id"]

    other = Org(name="Other")
    db_session.add(other)
    await db_session.commit()
    app.dependency_overrides[get_context] = lambda: RequestContext(other.id, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (await ac.get(f"/api/v1/invoices/{invoice_id}")).status_code == 404
        assert (await ac.get(f"/api/v1/invoices/{invoice_id}/status")).status_code == 404
