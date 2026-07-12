"""Invoice capture endpoints (PR-9).

Upload → hardening → storage → background extraction (Claude vision) →
human review → commit to price entries. Nothing auto-commits; extraction only
proposes. Org-scoped throughout; every mutation is audited.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ProblemException
from app.core.limiter import limiter
from app.db.session import get_session, get_session_factory
from app.deps import RequestContext, get_context
from app.models.enums import InvoiceStatus, LineMatchStatus, PriceSource
from app.models.invoice import Invoice, InvoiceLine
from app.models.price import PriceEntry
from app.repositories.ingredients import IngredientRepository
from app.repositories.invoices import InvoiceRepository
from app.repositories.stores import StoreRepository
from app.schemas.invoice import (
    CommitRequest,
    CommitResult,
    InvoiceLinePatch,
    InvoiceLineRead,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceRead,
    InvoiceStatusRead,
    MatchCandidate,
    StoreGuess,
)
from app.services import audit, invoice_matching
from app.services.image_prep import UploadError, prepare_upload
from app.services.invoice_extraction import get_invoice_extractor
from app.services.invoice_pipeline import base_price_preview, per_unit_price_cents, run_extraction
from app.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/invoices", tags=["invoices"])


# Overridable factories so tests can inject a Null extractor / in-memory storage.
def get_extractor() -> object | None:
    return get_invoice_extractor()


def get_storage() -> StorageService:
    return get_storage_service()


async def _line_read(
    session: AsyncSession, org_id: uuid.UUID, line: InvoiceLine, *, with_candidates: bool
) -> InvoiceLineRead:
    read = InvoiceLineRead.model_validate(line)
    preview, base_unit = base_price_preview(line)
    read.unit_price_per_base_cents = preview
    read.base_unit = base_unit
    if with_candidates and line.match_status in (
        LineMatchStatus.SUGGESTED,
        LineMatchStatus.UNMATCHED,
    ):
        query = line.description_en or line.raw_text
        read.candidates = [
            MatchCandidate(
                ingredient_id=c.ingredient_id,
                canonical_name_en=c.canonical_name_en,
                score=c.score,
            )
            for c in await invoice_matching.candidates_for(session, org_id, query)
        ]
    return read


@router.post(
    "",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an invoice photo/PDF (schedules extraction)",
)
@limiter.limit("30/minute")
async def upload_invoice(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
    file: UploadFile,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    storage: StorageService = Depends(get_storage),
    extractor: object | None = Depends(get_extractor),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> InvoiceRead:
    from app.core.config import settings

    data = await file.read()
    try:
        prepared = prepare_upload(
            data, max_mb=settings.max_upload_mb, max_pages=settings.max_pages
        )
    except UploadError as exc:
        raise ProblemException(
            status_code=exc.status, title="Invalid upload", detail=exc.detail
        ) from exc

    repo = InvoiceRepository(session, ctx.org_id)

    # Idempotent by content: re-uploading the same photo returns the existing row.
    existing = await repo.get_by_sha(prepared.sha256)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return await _to_invoice_read(session, ctx.org_id, existing, storage, with_lines=False)

    if await repo.count_created_today() >= settings.extractions_per_day:
        raise ProblemException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            title="Daily extraction limit reached",
            detail=f"This org is capped at {settings.extractions_per_day} invoices per day.",
            type_="https://rasoi.radar/problems/quota-exceeded",
        )

    key = f"invoices/{ctx.org_id}/{prepared.sha256}.{prepared.ext}"
    storage.put(key, prepared.stored_bytes, prepared.stored_content_type)

    invoice = Invoice(
        org_id=ctx.org_id,
        uploaded_by=ctx.user_id,
        image_ref=key,
        image_sha256=prepared.sha256,
        page_count=prepared.page_count,
        status=InvoiceStatus.UPLOADED,
    )
    session.add(invoice)
    await session.flush()
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="invoice.upload",
        entity="invoice",
        entity_id=invoice.id,
        meta={"sha256": prepared.sha256, "pages": prepared.page_count},
    )
    await session.commit()

    background_tasks.add_task(
        run_extraction,
        session_factory,
        invoice_id=invoice.id,
        org_id=ctx.org_id,
        extractor=extractor,
        images=prepared.images,
        content_sha=prepared.sha256,
    )
    return await _to_invoice_read(session, ctx.org_id, invoice, storage, with_lines=False)


async def _to_invoice_read(
    session: AsyncSession,
    org_id: uuid.UUID,
    invoice: Invoice,
    storage: StorageService,
    *,
    with_lines: bool,
) -> InvoiceRead:
    repo = InvoiceRepository(session, org_id)
    # Build from scalar columns only — model_validate would lazy-load `lines`.
    read = InvoiceRead(
        id=invoice.id,
        status=invoice.status,
        vendor_name_raw=invoice.vendor_name_raw,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        currency=invoice.currency,
        store_id=invoice.store_id,
        page_count=invoice.page_count,
        stated_total_cents=invoice.stated_total_cents,
        computed_total_cents=invoice.computed_total_cents,
        totals_match=invoice.totals_match,
        extraction_model=invoice.extraction_model,
        extraction_error=invoice.extraction_error,
        created_at=invoice.created_at,
        committed_at=invoice.committed_at,
    )
    read.line_count = await repo.line_count(invoice.id)
    signed = storage.signed_url(invoice.image_ref)
    read.signed_image_url = signed or f"/api/v1/invoices/{invoice.id}/image"
    guess = await invoice_matching.guess_store(session, org_id, invoice.vendor_name_raw)
    if guess is not None and invoice.store_id is None:
        read.store_guess = StoreGuess(store_id=guess.store_id, name=guess.name, score=guess.score)
    if with_lines:
        full = await repo.get_with_lines(invoice.id)
        assert full is not None
        read.lines = [
            await _line_read(session, org_id, line, with_candidates=True) for line in full.lines
        ]
    return read


@router.get("", response_model=InvoiceListResponse, summary="List invoices")
async def list_invoices(
    invoice_status: InvoiceStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> InvoiceListResponse:
    repo = InvoiceRepository(session, ctx.org_id)
    rows, total = await repo.list_page(
        status=invoice_status.value if invoice_status else None, page=page, page_size=page_size
    )
    items: list[InvoiceListItem] = []
    for inv, count in rows:
        item = InvoiceListItem.model_validate(inv)
        item.line_count = count
        items.append(item)
    return InvoiceListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{invoice_id}", response_model=InvoiceRead, summary="Invoice detail + lines")
async def get_invoice(
    invoice_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> InvoiceRead:
    repo = InvoiceRepository(session, ctx.org_id)
    invoice = await repo.get(invoice_id)
    if invoice is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Invoice not found",
            detail=f"No invoice {invoice_id} in this org.",
        )
    return await _to_invoice_read(session, ctx.org_id, invoice, storage, with_lines=True)


@router.get("/{invoice_id}/status", response_model=InvoiceStatusRead, summary="Cheap status poll")
async def invoice_status(
    invoice_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> InvoiceStatusRead:
    repo = InvoiceRepository(session, ctx.org_id)
    invoice = await repo.get(invoice_id)
    if invoice is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="Invoice not found"
        )
    return InvoiceStatusRead(
        status=invoice.status, line_count=await repo.line_count(invoice_id)
    )


@router.get("/{invoice_id}/image", summary="Stream the stored invoice image")
async def invoice_image(
    invoice_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    storage: StorageService = Depends(get_storage),
) -> Response:
    repo = InvoiceRepository(session, ctx.org_id)
    invoice = await repo.get(invoice_id)
    if invoice is None:
        raise ProblemException(status_code=status.HTTP_404_NOT_FOUND, title="Invoice not found")
    data = storage.get(invoice.image_ref)
    return Response(content=data, media_type="image/jpeg")


@router.patch(
    "/{invoice_id}/lines/{line_id}",
    response_model=InvoiceLineRead,
    summary="Edit an extracted line (reviewer)",
)
async def patch_line(
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
    payload: InvoiceLinePatch,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> InvoiceLineRead:
    repo = InvoiceRepository(session, ctx.org_id)
    line = await repo.get_line(line_id)
    if line is None or line.invoice_id != invoice_id:
        raise ProblemException(status_code=status.HTTP_404_NOT_FOUND, title="Line not found")

    fields = payload.model_dump(exclude_unset=True)
    if "matched_ingredient_id" in fields and fields["matched_ingredient_id"] is not None:
        ing = await IngredientRepository(session, ctx.org_id).get(fields["matched_ingredient_id"])
        if ing is None:
            raise ProblemException(
                status_code=status.HTTP_400_BAD_REQUEST,
                title="Unknown ingredient",
                detail="matched_ingredient_id is not an ingredient in this org.",
            )
    for name, value in fields.items():
        setattr(line, name, value)
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="invoice.line.edit",
        entity="invoice_line",
        entity_id=line.id,
        meta={"fields": list(fields.keys())},
    )
    await session.commit()
    await session.refresh(line)
    return await _line_read(session, ctx.org_id, line, with_candidates=True)


@router.post(
    "/{invoice_id}/commit", response_model=CommitResult, summary="Commit reviewed lines to prices"
)
async def commit_invoice(
    invoice_id: uuid.UUID,
    payload: CommitRequest,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> CommitResult:
    repo = InvoiceRepository(session, ctx.org_id)
    invoice = await repo.get_with_lines(invoice_id)
    if invoice is None:
        raise ProblemException(status_code=status.HTTP_404_NOT_FOUND, title="Invoice not found")
    if invoice.status not in (InvoiceStatus.NEEDS_REVIEW, InvoiceStatus.FAILED):
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            title="Invoice not reviewable",
            detail=f"Invoice is '{invoice.status.value}', not awaiting review.",
        )

    store = await StoreRepository(session, ctx.org_id).get(payload.store_id)
    if store is None:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Unknown store",
            detail="store_id is not a store in this org.",
        )

    selected = set(payload.line_ids) if payload.line_ids is not None else None
    observed = invoice.invoice_date or date.today()
    created = skipped = excluded = 0
    computed_total = 0

    for line in invoice.lines:
        chosen = selected is None or line.id in selected
        if not chosen:
            continue
        if line.match_status == LineMatchStatus.EXCLUDED or line.is_credit:
            excluded += 1
            continue
        if line.matched_ingredient_id is None:
            continue  # nothing to record without an ingredient
        price = per_unit_price_cents(line)
        if price is None or price <= 0 or line.pack_qty is None or line.pack_unit is None:
            continue

        if line.extended_cents is not None:
            computed_total += line.extended_cents

        if await repo.price_entry_exists(
            ingredient_id=line.matched_ingredient_id,
            store_id=store.id,
            observed_at=observed,
            price_cents=price,
        ):
            skipped += 1
            continue

        entry = PriceEntry(
            org_id=ctx.org_id,
            ingredient_id=line.matched_ingredient_id,
            store_id=store.id,
            brand=line.brand,
            pack_desc=line.pack_desc or (line.description_en or line.raw_text),
            pack_qty=line.pack_qty,
            pack_unit=line.pack_unit,
            price_cents=price,
            observed_at=observed,
            source=PriceSource.INVOICE,
            invoice_line_id=line.id,
            entered_by=ctx.user_id,
        )
        session.add(entry)
        await session.flush()
        line.created_price_entry_id = entry.id
        created += 1

    stated = invoice.stated_total_cents
    totals_match: bool | None = None
    if stated is not None:
        totals_match = abs(stated - computed_total) <= max(int(stated * 0.02), 100)

    invoice.store_id = store.id
    invoice.computed_total_cents = computed_total
    invoice.totals_match = totals_match
    invoice.status = InvoiceStatus.COMMITTED
    from datetime import UTC, datetime

    invoice.committed_at = datetime.now(UTC)
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="invoice.commit",
        entity="invoice",
        entity_id=invoice.id,
        meta={
            "created": created,
            "skipped": skipped,
            "excluded": excluded,
            "store_id": str(store.id),
        },
    )
    await session.commit()
    return CommitResult(
        invoice_id=invoice.id,
        created=created,
        skipped_duplicates=skipped,
        excluded=excluded,
        totals_match=totals_match,
    )


@router.post("/{invoice_id}/reject", response_model=InvoiceStatusRead, summary="Reject an invoice")
async def reject_invoice(
    invoice_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> InvoiceStatusRead:
    repo = InvoiceRepository(session, ctx.org_id)
    invoice = await repo.get(invoice_id)
    if invoice is None:
        raise ProblemException(status_code=status.HTTP_404_NOT_FOUND, title="Invoice not found")
    invoice.status = InvoiceStatus.REJECTED
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="invoice.reject",
        entity="invoice",
        entity_id=invoice.id,
    )
    await session.commit()
    return InvoiceStatusRead(status=invoice.status, line_count=await repo.line_count(invoice_id))
