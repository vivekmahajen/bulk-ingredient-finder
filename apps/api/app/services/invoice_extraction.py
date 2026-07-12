"""Invoice line-item extraction (Claude vision).

Mirrors the provider-Protocol + ``configured=False`` fallback used by
``price_discovery`` and ``translation``:
  * ``ClaudeInvoiceExtractor`` — Anthropic Messages API, images as base64 blocks,
    the verbatim system prompt below, temperature 0, retries + circuit breaker.
  * ``NullInvoiceExtractor`` — returns fixture JSON keyed by content sha (tests);
    empty result when no fixture is registered. The factory returns ``None`` when
    no API key is configured, exactly like ``get_discovery_service``.

Extraction PROPOSES; nothing is committed without human review.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.translation import CircuitBreaker

logger = get_logger("invoice_extraction")

_ANTHROPIC_BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
_ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = """\
You are an invoice line-item extractor for restaurant supply invoices. You read
invoices in ANY language or mixed languages (English, Hindi/Devanagari,
romanized Hindi, Punjabi, Gujarati, Spanish) including thermal receipts and
handwritten totals.

Return ONLY valid JSON matching this schema, no prose:

{
  "vendor_name": string|null,      // as printed, original script
  "invoice_number": string|null,
  "invoice_date": "YYYY-MM-DD"|null,
  "currency": "USD"|string,
  "stated_total_cents": int|null,  // grand total as printed, in cents
  "lines": [{
    "line_no": int,
    "raw_text": string,            // verbatim, preserve original script
    "raw_lang": "en"|"hi"|"es"|"mixed"|string,
    "description_en": string,      // faithful English rendering; transliterate
                                   // brand names, translate item words
                                   // (e.g. "बासमती चावल" -> "basmati rice")
    "brand": string|null,          // SWAD, Laxmi, Deep, etc.
    "pack_desc": string,           // verbatim pack notation, e.g. "6/#10", "4x5 LB", "बोरी 25kg"
    "case_count": int|null,        // 6 for "6/#10"
    "pack_qty": number|null,       // per-unit size: 10 for #10 can? NO — see rules
    "pack_unit": "kg"|"g"|"lb"|"oz"|"l"|"ml"|"gal"|"each"|null,
    "quantity_ordered": number,    // cases or units bought on this line
    "unit_price_cents": int|null,  // price per case/unit as invoiced
    "extended_cents": int|null,    // line total
    "is_credit": boolean,          // returns/credits (negative lines)
    "confidence": number           // 0..1 for THIS line's numeric fields
  }]
}

Rules:
- TOTAL pack math: "6/#10" means a case of six #10 cans (~2.84 kg each) ->
  case_count=6, pack_qty=2.84, pack_unit="kg". "4x5 LB" -> case_count=4,
  pack_qty=5, pack_unit="lb". Single "25 kg" bag -> case_count=1, pack_qty=25.
- Catch-weight items (meat priced per lb with a weight column): set pack_unit
  to the weight unit, pack_qty to the actual weight, unit_price_cents to the
  per-unit price, extended_cents to the line total.
- Never invent numbers. Illegible -> null with low confidence. Do not guess a
  total that is not printed.
- Skip non-product lines (delivery fee, tax, deposit) EXCEPT list them with
  is_credit=false, pack_unit=null and description_en prefixed "FEE: " so the
  reviewer can exclude them consciously.
- Credits/returns: is_credit=true, amounts positive.
- Dates: prefer the invoice date over order/ship dates; DD/MM vs MM/DD -> use
  vendor country context (US default MM/DD).
- confidence reflects the numbers, not the language. A crisp Hindi line can be 0.98.
"""


@dataclass(frozen=True)
class ExtractionHints:
    store_names: list[str] = field(default_factory=list)
    ingredient_names: list[str] = field(default_factory=list)
    content_sha: str | None = None  # lets NullInvoiceExtractor pick the fixture
    country: str = "US"


@dataclass(frozen=True)
class ExtractedLine:
    line_no: int
    raw_text: str
    raw_lang: str | None
    description_en: str | None
    brand: str | None
    pack_desc: str | None
    case_count: int | None
    pack_qty: float | None
    pack_unit: str | None
    quantity_ordered: float | None
    unit_price_cents: int | None
    extended_cents: int | None
    is_credit: bool
    confidence: float


@dataclass(frozen=True)
class ExtractionResult:
    vendor_name: str | None
    invoice_number: str | None
    invoice_date: date | None
    currency: str
    stated_total_cents: int | None
    lines: list[ExtractedLine]
    model: str
    latency_ms: int


class ExtractionUnavailable(Exception):
    pass


# --- parsing helpers ----------------------------------------------------------


def _extract_json(text: str) -> dict[str, object] | None:
    if not text:
        return None
    candidate = text
    if "```" in candidate:
        for part in candidate.split("```"):
            p = part.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                candidate = p
                break
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(candidate[start : end + 1])
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def _as_int(v: object) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return round(v)
    return None


def _as_float(v: object) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _as_str(v: object) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _parse_date(v: object) -> date | None:
    if not isinstance(v, str):
        return None
    try:
        return date.fromisoformat(v.strip()[:10])
    except ValueError:
        return None


def result_from_json(raw: dict[str, object], *, model: str, latency_ms: int) -> ExtractionResult:
    lines_raw = raw.get("lines")
    lines: list[ExtractedLine] = []
    if isinstance(lines_raw, list):
        for i, item in enumerate(lines_raw):
            if not isinstance(item, dict):
                continue
            raw_text = _as_str(item.get("raw_text")) or _as_str(item.get("description_en")) or ""
            if not raw_text:
                continue
            conf = _as_float(item.get("confidence"))
            lines.append(
                ExtractedLine(
                    line_no=_as_int(item.get("line_no")) or (i + 1),
                    raw_text=raw_text,
                    raw_lang=_as_str(item.get("raw_lang")),
                    description_en=_as_str(item.get("description_en")),
                    brand=_as_str(item.get("brand")),
                    pack_desc=_as_str(item.get("pack_desc")),
                    case_count=_as_int(item.get("case_count")),
                    pack_qty=_as_float(item.get("pack_qty")),
                    pack_unit=_as_str(item.get("pack_unit")),
                    quantity_ordered=_as_float(item.get("quantity_ordered")),
                    unit_price_cents=_as_int(item.get("unit_price_cents")),
                    extended_cents=_as_int(item.get("extended_cents")),
                    is_credit=bool(item.get("is_credit", False)),
                    confidence=max(0.0, min(1.0, conf if conf is not None else 0.0)),
                )
            )
    currency = _as_str(raw.get("currency")) or "USD"
    return ExtractionResult(
        vendor_name=_as_str(raw.get("vendor_name")),
        invoice_number=_as_str(raw.get("invoice_number")),
        invoice_date=_parse_date(raw.get("invoice_date")),
        currency=currency[:3].upper(),
        stated_total_cents=_as_int(raw.get("stated_total_cents")),
        lines=lines,
        model=model,
        latency_ms=latency_ms,
    )


# --- providers ----------------------------------------------------------------


class ClaudeInvoiceExtractor:
    name = "claude"

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        timeout_s: float,
        retries: int,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._retries = retries
        self._breaker = CircuitBreaker()
        self._url = f"{(base_url or _ANTHROPIC_BASE).rstrip('/')}/v1/messages"

    def _user_content(self, images: list[bytes], hints: ExtractionHints) -> list[dict[str, object]]:
        content: list[dict[str, object]] = []
        for img in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(img).decode("ascii"),
                    },
                }
            )
        grounding = ""
        if hints.store_names:
            grounding += "Known stores (for vendor grounding): " + "; ".join(
                hints.store_names[:50]
            )
        if hints.ingredient_names:
            grounding += "\nKnown ingredients (for item naming, do NOT output IDs): " + "; ".join(
                hints.ingredient_names[:100]
            )
        content.append(
            {
                "type": "text",
                "text": (
                    f"Extract every line item from this invoice (vendor country: {hints.country}). "
                    "Return ONLY the JSON object.\n" + grounding
                ),
            }
        )
        return content

    async def extract(self, images: list[bytes], hints: ExtractionHints) -> ExtractionResult:
        if self._breaker.is_open:
            raise ExtractionUnavailable("circuit open")
        body = {
            "model": self._model,
            "max_tokens": 4000,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": self._user_content(images, hints)}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        started = time.monotonic()
        last_exc: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.post(self._url, headers=headers, json=body)
                    resp.raise_for_status()
                    data = resp.json()
                text = "".join(
                    b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
                )
                parsed = _extract_json(text)
                if parsed is None:
                    raise ExtractionUnavailable("model did not return parseable JSON")
                self._breaker.record_success()
                latency = int((time.monotonic() - started) * 1000)
                return result_from_json(parsed, model=self._model, latency_ms=latency)
            except Exception as exc:  # noqa: BLE001 - uniform retry handling
                last_exc = exc
                self._breaker.record_failure()
                logger.warning("extraction_attempt_failed", attempt=attempt, error=str(exc))
        raise ExtractionUnavailable(str(last_exc))


class NullInvoiceExtractor:
    """Fixture-backed extractor for tests; empty result when no fixture matches."""

    name = "null"

    def __init__(self, fixtures: dict[str, dict[str, object]] | None = None) -> None:
        self._fixtures = fixtures or {}

    async def extract(self, images: list[bytes], hints: ExtractionHints) -> ExtractionResult:
        raw = self._fixtures.get(hints.content_sha or "")
        if raw is None:
            return ExtractionResult(
                vendor_name=None,
                invoice_number=None,
                invoice_date=None,
                currency="USD",
                stated_total_cents=None,
                lines=[],
                model="null",
                latency_ms=0,
            )
        return result_from_json(raw, model="null", latency_ms=0)


def get_invoice_extractor() -> ClaudeInvoiceExtractor | NullInvoiceExtractor | None:
    """Configured extractor, or None when extraction isn't set up."""
    provider = settings.extract_provider.lower()
    if provider == "null":
        return NullInvoiceExtractor()
    if provider == "claude" and settings.anthropic_api_key:
        return ClaudeInvoiceExtractor(
            settings.anthropic_api_key,
            model=settings.extraction_model,
            timeout_s=settings.extraction_timeout_s,
            retries=settings.extraction_retries,
        )
    return None
