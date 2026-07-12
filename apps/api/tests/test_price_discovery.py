"""Web price-discovery service: parsing, normalization, ranking, degradation."""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Org
from app.services import price_discovery
from app.services.price_discovery import (
    ClaudeWebSearchProvider,
    DiscoveryQuery,
    DiscoveryUnavailable,
    PriceDiscoveryService,
    _extract_json,
    _to_seller,
    get_discovery_service,
)
from app.services.translation import DetectionResult, TranslationService, get_translation_service


class _EnglishProvider:
    name = "test"

    async def detect(self, text: str) -> DetectionResult:
        return DetectionResult(lang="en", confidence=0.95, candidates=["en"])

    async def translate(self, text: str, *, source: str, target: str = "en") -> str:
        return text

    async def romanize(self, text: str, *, source: str) -> str | None:
        return None


def test_extract_json_tolerates_fences_and_prose() -> None:
    assert _extract_json('```json\n{"sellers": [], "notes": []}\n```') == {
        "sellers": [],
        "notes": [],
    }
    assert _extract_json('Here you go: {"sellers": []} — hope that helps') == {"sellers": []}
    assert _extract_json("no json here") is None
    assert _extract_json("") is None


def test_to_seller_normalizes_unit_price() -> None:
    seller = _to_seller(
        {
            "name": "Restaurant Depot",
            "price_cents": 5200,
            "pack_qty": 40,
            "pack_unit": "lb",
            "pack_desc": "40 lb case",
            "url": "https://example.com/x",
        }
    )
    assert seller is not None
    assert seller.base_unit == "kg"
    # $52 / (40 lb -> 18.14 kg) ≈ 286.6 cents/kg
    assert seller.unit_price_cents is not None
    assert 286 <= seller.unit_price_cents <= 287


def test_to_seller_handles_missing_price() -> None:
    seller = _to_seller({"name": "Local Co-op", "price_text": "call for pricing"})
    assert seller is not None
    assert seller.price_cents is None
    assert seller.unit_price_cents is None
    assert seller.base_unit is None


def test_to_seller_rejects_nameless_rows() -> None:
    assert _to_seller({"price_cents": 100}) is None
    assert _to_seller({"name": "   "}) is None
    assert _to_seller("not a dict") is None


class _FakeProvider:
    name = "fake"

    def __init__(self, result=None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc

    async def discover(self, q: DiscoveryQuery):
        if self._exc is not None:
            raise self._exc
        return self._result


@pytest.mark.asyncio
async def test_service_sorts_cheapest_first_priced_before_unpriced() -> None:
    rows = [
        {"name": "Pricey", "price_cents": 8000, "pack_qty": 40, "pack_unit": "lb"},
        {"name": "No price", "price_text": "quote only"},
        {"name": "Cheap", "price_cents": 4000, "pack_qty": 40, "pack_unit": "lb"},
    ]
    service = PriceDiscoveryService(_FakeProvider(result=(rows, ["membership required"])))
    sellers, notes = await service.discover(DiscoveryQuery(ingredient_name="Cauliflower"))
    assert [s.name for s in sellers] == ["Cheap", "Pricey", "No price"]
    assert notes == ["membership required"]


def _mock_anthropic(monkeypatch: pytest.MonkeyPatch, responses: list[dict]) -> list[int]:
    """Patch httpx.AsyncClient so the provider talks to a canned transport.

    Returns a one-element list holding the request count.
    """
    queue = iter(responses)
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(200, json=next(queue))

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        return real(transport=transport)

    monkeypatch.setattr(price_discovery.httpx, "AsyncClient", factory)
    return calls


@pytest.mark.asyncio
async def test_provider_resumes_on_pause_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _mock_anthropic(
        monkeypatch,
        [
            # Round 1: server paused mid-search, no JSON yet.
            {
                "stop_reason": "pause_turn",
                "content": [
                    {"type": "text", "text": "Let me search for suppliers…"},
                    {"type": "server_tool_use", "name": "web_search"},
                ],
            },
            # Round 2: final answer with the JSON payload.
            {
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": '{"sellers":[{"name":"Restaurant Depot","price_cents":4000,'
                        '"pack_qty":40,"pack_unit":"lb"}],"notes":["membership required"]}',
                    }
                ],
            },
        ],
    )
    provider = ClaudeWebSearchProvider("k", model="m", timeout_s=5)
    sellers, notes = await provider.discover(DiscoveryQuery(ingredient_name="Cauliflower"))
    assert calls[0] == 2  # resumed the paused turn
    assert sellers[0]["name"] == "Restaurant Depot"
    assert notes == ["membership required"]


@pytest.mark.asyncio
async def test_provider_raises_with_stop_reason_when_no_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_anthropic(
        monkeypatch,
        [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "sorry, no data"}]}],
    )
    provider = ClaudeWebSearchProvider("k", model="m", timeout_s=5)
    with pytest.raises(DiscoveryUnavailable, match="stop=end_turn"):
        await provider.discover(DiscoveryQuery(ingredient_name="Cauliflower"))


@pytest.mark.asyncio
async def test_service_degrades_on_provider_error() -> None:
    service = PriceDiscoveryService(_FakeProvider(exc=DiscoveryUnavailable("boom")))
    sellers, notes = await service.discover(DiscoveryQuery(ingredient_name="Cauliflower"))
    assert sellers == []
    assert notes and "didn't return" in notes[0]

    service2 = PriceDiscoveryService(_FakeProvider(exc=RuntimeError("network")))
    sellers2, notes2 = await service2.discover(DiscoveryQuery(ingredient_name="Cauliflower"))
    assert sellers2 == []
    assert notes2 and "unavailable" in notes2[0]


def test_get_discovery_service_none_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "discovery_provider", "claude")
    monkeypatch.setattr(config.settings, "anthropic_api_key", "")
    assert get_discovery_service() is None

    monkeypatch.setattr(config.settings, "anthropic_api_key", "sk-test")
    assert get_discovery_service() is not None


@pytest.mark.asyncio
async def test_discover_endpoint_reports_unconfigured(
    db_session: AsyncSession, app, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "anthropic_api_key", "")  # ensure not configured
    db_session.add(Org(name="Hari Om"))
    await db_session.commit()
    app.dependency_overrides[get_translation_service] = lambda: TranslationService(
        _EnglishProvider()
    )

    created = await client.post(
        "/api/v1/ingredients",
        json={"display_name": "Cauliflower", "source_lang": "en"},
    )
    assert created.status_code == 201, created.text
    ingredient_id = created.json()["id"]

    resp = await client.get(f"/api/v1/ingredients/{ingredient_id}/discover-prices?radius_miles=25")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["configured"] is False
    assert body["sellers"] == []
    assert "Cauliflower" in body["query"]
    assert any("ANTHROPIC_API_KEY" in n for n in body["notes"])
