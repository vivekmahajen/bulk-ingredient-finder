"""Web price discovery.

Finds *estimated* bulk sellers + prices for an ingredient from the open web,
so a user can seed a brand-new ingredient with candidate suppliers before any
price has been logged by hand.

The default provider drives the Anthropic Messages API with its web-search tool
(``DISCOVERY_PROVIDER=claude`` + ``ANTHROPIC_API_KEY``). It is strictly optional:
with no key configured the service reports ``configured=False`` and the UI shows
a "connect a provider" state — nothing else in the app depends on it. Results
are best-effort estimates and are always labeled as such.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.discovery import DiscoveredSeller
from app.units import PackUnit, base_unit_of, unit_price_cents_per_base

logger = get_logger("price_discovery")

_ANTHROPIC_BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_SELLERS = 6
# Enough searches to actually open listing pages and read prices — pricing
# takes a couple of extra lookups beyond just naming a seller.
_MAX_WEB_SEARCHES = 6


class DiscoveryUnavailable(Exception):
    """Raised when a configured provider fails to return usable results."""


class DiscoveryProvider(Protocol):
    name: str

    async def discover(
        self, q: DiscoveryQuery
    ) -> tuple[list[dict[str, object]], list[str]]: ...


@dataclass(frozen=True)
class DiscoveryQuery:
    ingredient_name: str
    aliases: list[str] = field(default_factory=list)
    location: str | None = None
    radius_miles: float | None = None


def _prompt(q: DiscoveryQuery) -> str:
    also = f" (also known as: {', '.join(q.aliases)})" if q.aliases else ""
    where = (
        f"near {q.location}, within about {q.radius_miles:.0f} miles"
        if q.location and q.radius_miles
        else (f"near {q.location}" if q.location else "in the United States")
    )
    return (
        f"Find suppliers selling **{q.ingredient_name}**{also} in bulk/wholesale "
        f"quantities for a restaurant, {where}, AND the actual price each one "
        f"charges.\n\n"
        "Your #1 job is to return REAL, CURRENT prices — not just names. For each "
        "candidate seller, OPEN its product / pricing page and read the listed price "
        "for a bulk pack (e.g. a 20 lb bag, a #10 case). Use up to "
        f"{_MAX_WEB_SEARCHES} searches and read the actual listings, don't stop at the "
        "first result snippet.\n\n"
        "Strongly prefer sellers whose price is publicly listed online so the user "
        "sees a concrete number — reputable national restaurant-supply and bulk "
        "retailers (e.g. WebstaurantStore, Amazon Business, Costco Business, Restaurant "
        "Depot online, ethnic-grocery e-commerce) usually publish prices. Also include "
        "nearby cash-and-carry / ethnic wholesalers / produce houses even if their "
        "price is gated.\n\n"
        f"Return ONLY a JSON object (no prose, no markdown fences) shaped exactly:\n"
        '{"sellers":[{"name":str,"price_text":str|null,"price_cents":int|null,'
        '"pack_desc":str|null,"pack_qty":number|null,'
        '"pack_unit":"kg"|"g"|"lb"|"oz"|"l"|"ml"|"gal"|"each"|null,'
        '"url":str|null,"location":str|null,"distance_note":str|null,'
        '"snippet":str|null}],"notes":[str]}\n\n'
        "Rules: price_cents is the TOTAL pack price in US cents (integer) read from the "
        "seller's listing; pack_qty/pack_unit describe that pack (e.g. 20 + 'lb'). set "
        "url to the exact product/pricing page you read the price from. When a price is "
        "genuinely not public (login/quote/membership only), still list the seller but "
        "put a short reason in price_text (e.g. 'Login required for price') and leave "
        "price_cents null. Never invent a number — but do the extra searches needed to "
        f"attach a real price to as many sellers as possible. At most {_MAX_SELLERS} "
        "sellers, cheapest concrete price first, unpriced sellers last."
    )


class ClaudeWebSearchProvider:
    name = "claude"

    # Server-side web search can return stop_reason="pause_turn" partway through a
    # long turn; you resume by sending the assistant's content back. Cap the
    # number of resumes so a runaway turn can't loop forever.
    _MAX_ROUNDS = 5

    def __init__(
        self, api_key: str, *, model: str, timeout_s: float, base_url: str | None = None
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        base = (base_url or _ANTHROPIC_BASE).rstrip("/")
        self._url = f"{base}/v1/messages"

    async def discover(self, q: DiscoveryQuery) -> tuple[list[dict[str, object]], list[str]]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        messages: list[dict[str, object]] = [{"role": "user", "content": _prompt(q)}]
        texts: list[str] = []
        last_round_text = ""
        stop_reason: str | None = None

        timeout = httpx.Timeout(self._timeout_s, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for _ in range(self._MAX_ROUNDS):
                body = {
                    "model": self._model,
                    "max_tokens": 3000,
                    "tools": [
                        {
                            "type": "web_search_20250305",
                            "name": "web_search",
                            "max_uses": _MAX_WEB_SEARCHES,
                        }
                    ],
                    "messages": messages,
                }
                resp = await client.post(self._url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("content", []) or []
                round_text = "".join(
                    b.get("text", "") for b in content if b.get("type") == "text"
                )
                if round_text:
                    texts.append(round_text)
                    last_round_text = round_text
                stop_reason = data.get("stop_reason")
                if stop_reason == "pause_turn":
                    # Resume the paused turn by echoing the assistant content back.
                    messages.append({"role": "assistant", "content": content})
                    continue
                break

        # The final JSON is in the last round; fall back to the concatenation.
        parsed = _extract_json(last_round_text.strip()) or _extract_json("".join(texts).strip())
        if parsed is None:
            logger.warning(
                "discovery_unparseable",
                stop_reason=stop_reason,
                text_chars=len(last_round_text),
            )
            raise DiscoveryUnavailable(f"unparseable model reply (stop={stop_reason})")
        sellers_obj = parsed.get("sellers")
        notes_obj = parsed.get("notes")
        sellers = sellers_obj if isinstance(sellers_obj, list) else []
        notes = [str(n) for n in notes_obj] if isinstance(notes_obj, list) else []
        return sellers, notes


def _extract_json(text: str) -> dict[str, object] | None:
    """Pull a JSON object out of the model's reply, tolerating stray prose/fences."""
    if not text:
        return None
    candidate = text
    if "```" in candidate:
        # Strip a ```json … ``` fence if present.
        parts = candidate.split("```")
        for part in parts:
            p = part.strip()
            if p.startswith("json"):
                p = p[len("json") :].strip()
            if p.startswith("{"):
                candidate = p
                break
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(candidate[start : end + 1])
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


class PriceDiscoveryService:
    """Wraps a provider; normalizes + bounds results, never raises to the caller."""

    def __init__(self, provider: DiscoveryProvider) -> None:
        self._provider = provider

    async def discover(self, q: DiscoveryQuery) -> tuple[list[DiscoveredSeller], list[str]]:
        try:
            raw, notes = await self._provider.discover(q)
        except DiscoveryUnavailable as exc:
            logger.warning("discovery_no_results", error=str(exc))
            return [], [f"The web search didn't return usable results ({exc}). Try again shortly."]
        except httpx.HTTPStatusError as exc:
            detail = f"{exc.response.status_code}"
            try:
                err = exc.response.json().get("error", {})
                code = exc.response.status_code
                detail = f"{code} {err.get('type', '')}: {err.get('message', '')}"
            except Exception:  # noqa: BLE001 — best-effort error surfacing
                pass
            logger.warning("discovery_http_error", detail=detail)
            return [], [f"Web price discovery call failed ({detail})."]
        except Exception as exc:  # noqa: BLE001 — degrade, never break the request
            logger.warning("discovery_failed", error=f"{type(exc).__name__}: {exc}")
            return [], [f"Web price discovery is temporarily unavailable ({type(exc).__name__})."]

        sellers = [s for s in (_to_seller(item) for item in raw[:_MAX_SELLERS]) if s is not None]
        # Cheapest first when we could normalize a unit price; unpriced sink last.
        sellers.sort(key=lambda s: (s.unit_price_cents is None, s.unit_price_cents or 0.0))
        return sellers, notes


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_seller(item: object) -> DiscoveredSeller | None:
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    price_cents = _coerce_int(item.get("price_cents"))
    pack_qty = _coerce_float(item.get("pack_qty"))
    pack_unit_raw = item.get("pack_unit")
    pack_unit = pack_unit_raw if isinstance(pack_unit_raw, str) else None

    unit_price_cents: float | None = None
    base_unit: str | None = None
    if price_cents and price_cents > 0 and pack_qty and pack_qty > 0 and pack_unit:
        try:
            unit = PackUnit(pack_unit)
            unit_price_cents = float(
                unit_price_cents_per_base(
                    price_cents=price_cents, pack_qty=Decimal(str(pack_qty)), pack_unit=unit
                )
            )
            base_unit = base_unit_of(unit)
        except (ValueError, KeyError, InvalidOperation):
            unit_price_cents = None
            base_unit = None

    def _str(key: str) -> str | None:
        v = item.get(key)
        return v.strip() if isinstance(v, str) and v.strip() else None

    return DiscoveredSeller(
        name=name.strip(),
        price_text=_str("price_text"),
        price_cents=price_cents if (price_cents and price_cents > 0) else None,
        pack_desc=_str("pack_desc"),
        pack_qty=pack_qty,
        pack_unit=pack_unit if base_unit is not None else (pack_unit or None),
        unit_price_cents=unit_price_cents,
        base_unit=base_unit,
        url=_str("url"),
        location=_str("location"),
        distance_note=_str("distance_note"),
        snippet=_str("snippet"),
    )


def get_discovery_service() -> PriceDiscoveryService | None:
    """The configured service, or None when discovery isn't set up."""
    if settings.discovery_provider.lower() != "claude" or not settings.anthropic_api_key:
        return None
    return PriceDiscoveryService(
        ClaudeWebSearchProvider(
            settings.anthropic_api_key,
            model=settings.discovery_model,
            timeout_s=settings.discovery_timeout_s,
            base_url=_ANTHROPIC_BASE,
        )
    )
