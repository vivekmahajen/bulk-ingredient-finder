"""Invoice-capture API schemas (PR-9)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InvoiceStatus, LineMatchStatus, PackUnit


class MatchCandidate(BaseModel):
    ingredient_id: uuid.UUID
    canonical_name_en: str
    score: float


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    raw_text: str
    raw_lang: str | None = None
    description_en: str | None = None
    brand: str | None = None
    pack_desc: str | None = None
    pack_qty: float | None = None
    pack_unit: PackUnit | None = None
    case_count: int | None = None
    unit_price_cents: int | None = None
    extended_cents: int | None = None
    is_credit: bool = False
    confidence: float
    match_status: LineMatchStatus
    matched_ingredient_id: uuid.UUID | None = None
    match_score: float | None = None
    created_price_entry_id: uuid.UUID | None = None
    # Server-computed comparison preview (per base unit), never trusted from client.
    unit_price_per_base_cents: float | None = None
    base_unit: str | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)


class StoreGuess(BaseModel):
    store_id: uuid.UUID
    name: str
    score: float


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: InvoiceStatus
    vendor_name_raw: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    currency: str = "USD"
    store_id: uuid.UUID | None = None
    page_count: int = 1
    stated_total_cents: int | None = None
    computed_total_cents: int | None = None
    totals_match: bool | None = None
    extraction_model: str | None = None
    extraction_error: str | None = None
    created_at: datetime
    committed_at: datetime | None = None
    line_count: int = 0
    # Not persisted: recomputed each read (extraction only *guesses* the store).
    store_guess: StoreGuess | None = None
    signed_image_url: str | None = None
    lines: list[InvoiceLineRead] = Field(default_factory=list)


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: InvoiceStatus
    vendor_name_raw: str | None = None
    invoice_date: date | None = None
    stated_total_cents: int | None = None
    totals_match: bool | None = None
    line_count: int = 0
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    page: int
    page_size: int
    total: int


class InvoiceStatusRead(BaseModel):
    status: InvoiceStatus
    line_count: int


class InvoiceLinePatch(BaseModel):
    """Reviewer edits. Only provided fields are changed."""

    raw_text: str | None = None
    raw_lang: str | None = None
    description_en: str | None = None
    brand: str | None = None
    pack_desc: str | None = None
    pack_qty: float | None = None
    pack_unit: PackUnit | None = None
    case_count: int | None = None
    unit_price_cents: int | None = None
    extended_cents: int | None = None
    is_credit: bool | None = None
    matched_ingredient_id: uuid.UUID | None = None
    match_status: LineMatchStatus | None = None


class CommitRequest(BaseModel):
    store_id: uuid.UUID
    line_ids: list[uuid.UUID] | None = None


class CommitResult(BaseModel):
    invoice_id: uuid.UUID
    created: int
    skipped_duplicates: int
    excluded: int
    totals_match: bool | None = None
