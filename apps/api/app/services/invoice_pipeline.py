"""Invoice pipeline: background extraction runner + shared line math.

All numeric unit conversion goes through ``app.units`` (never duplicated). The
only arithmetic here is dividing a case price into a per-single-unit price
(``unit_price / case_count``), which is not a unit conversion.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.enums import InvoiceStatus, PackUnit
from app.models.invoice import Invoice, InvoiceLine
from app.repositories.invoices import InvoiceRepository
from app.services import invoice_matching
from app.services.invoice_extraction import ExtractionHints, ExtractionResult
from app.units import base_unit_of, unit_price_cents_per_base

logger = get_logger("invoice_pipeline")

_PACK_UNIT_VALUES = {u.value for u in PackUnit}


def coerce_pack_unit(value: str | None) -> PackUnit | None:
    if value and value in _PACK_UNIT_VALUES:
        return PackUnit(value)
    return None


def per_unit_price_cents(line: InvoiceLine) -> int | None:
    """Price of one purchasable pack of ``pack_qty pack_unit``.

    Case-packed (``case_count > 1``): the invoiced ``unit_price_cents`` is the
    case price, so one inner pack costs ``unit_price_cents / case_count``.
    Single packs and catch-weight lines: the whole ``pack_qty`` is one pack, so
    the price is the line total (``extended_cents``), falling back to
    ``unit_price_cents``.
    """
    if line.case_count and line.case_count > 1 and line.unit_price_cents is not None:
        return round(line.unit_price_cents / line.case_count)
    if line.extended_cents is not None:
        return line.extended_cents
    return line.unit_price_cents


def base_price_preview(line: InvoiceLine) -> tuple[float | None, str | None]:
    """($ per base unit, base unit) for the review preview — via app.units."""
    price = per_unit_price_cents(line)
    if price is None or line.pack_qty is None or line.pack_unit is None:
        return None, None
    try:
        qty = Decimal(str(line.pack_qty))
        if qty <= 0:
            return None, None
        unit = PackUnit(line.pack_unit)
        value = float(unit_price_cents_per_base(price_cents=price, pack_qty=qty, pack_unit=unit))
        return value, base_unit_of(unit)
    except (ValueError, KeyError, InvalidOperation):
        return None, None


async def _build_hints(repo: InvoiceRepository, content_sha: str) -> ExtractionHints:
    return ExtractionHints(
        store_names=await repo.hint_store_names(),
        ingredient_names=await repo.hint_ingredient_names(),
        content_sha=content_sha,
    )


def _persist_result(
    invoice: Invoice, result: ExtractionResult, org_id: uuid.UUID
) -> list[InvoiceLine]:
    invoice.vendor_name_raw = result.vendor_name
    invoice.invoice_number = result.invoice_number
    invoice.invoice_date = result.invoice_date
    invoice.currency = result.currency or "USD"
    invoice.stated_total_cents = result.stated_total_cents
    invoice.extraction_model = result.model
    invoice.extraction_ms = result.latency_ms
    lines: list[InvoiceLine] = []
    for el in result.lines:
        line = InvoiceLine(
            org_id=org_id,
            invoice_id=invoice.id,
            line_no=el.line_no,
            raw_text=el.raw_text,
            raw_lang=el.raw_lang,
            description_en=el.description_en,
            brand=el.brand,
            pack_desc=el.pack_desc,
            pack_qty=el.pack_qty,
            pack_unit=coerce_pack_unit(el.pack_unit),
            case_count=el.case_count,
            unit_price_cents=el.unit_price_cents,
            extended_cents=el.extended_cents,
            is_credit=el.is_credit,
            confidence=el.confidence,
        )
        lines.append(line)
    return lines


async def run_extraction(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    invoice_id: uuid.UUID,
    org_id: uuid.UUID,
    extractor: object | None,
    images: list[bytes],
    content_sha: str,
) -> None:
    """Background task: extract → persist lines → match → needs_review/failed."""
    async with session_factory() as session:
        repo = InvoiceRepository(session, org_id)
        invoice = await repo.get(invoice_id)
        if invoice is None:
            return
        invoice.status = InvoiceStatus.EXTRACTING
        await session.commit()

        try:
            if extractor is None:
                raise RuntimeError(
                    "Invoice extraction isn't configured "
                    "(set EXTRACT_PROVIDER + ANTHROPIC_API_KEY)."
                )
            hints = await _build_hints(repo, content_sha)
            result: ExtractionResult = await extractor.extract(images, hints)  # type: ignore[attr-defined]

            lines = _persist_result(invoice, result, org_id)
            for line in lines:
                session.add(line)
            await session.flush()
            await invoice_matching.match_lines(session, org_id, lines)
            invoice.status = InvoiceStatus.NEEDS_REVIEW
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - failures are surfaced on the row
            logger.warning("extraction_failed", invoice_id=str(invoice_id), error=str(exc))
            await session.rollback()
            failed = await InvoiceRepository(session, org_id).get(invoice_id)
            if failed is not None:
                failed.status = InvoiceStatus.FAILED
                failed.extraction_error = str(exc)[:500]
                await session.commit()
