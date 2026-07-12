"""Invoice-capture models (PR-9).

An ``Invoice`` is a photographed/scanned supplier invoice. Extraction (Claude
vision) proposes ``InvoiceLine`` rows; nothing becomes a ``PriceEntry`` until a
human reviews and commits. Idempotency is by image content
(``UNIQUE(org_id, image_sha256)``) so re-uploading the same photo returns the
existing invoice rather than duplicating work.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, UUIDPrimaryKeyMixin
from app.models._sa_enum import pg_enum
from app.models.enums import InvoiceStatus, LineMatchStatus, PackUnit


class Invoice(UUIDPrimaryKeyMixin, OrgScopedMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("org_id", "image_sha256", name="uq_invoice_org_sha256"),)

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Store is a *guess* at extraction time; only set for real at review/commit.
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vendor_name_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="USD", server_default="USD"
    )

    image_ref: Mapped[str] = mapped_column(Text, nullable=False)
    image_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    status: Mapped[InvoiceStatus] = mapped_column(
        pg_enum(InvoiceStatus, "invoice_status"),
        nullable=False,
        default=InvoiceStatus.UPLOADED,
        server_default=InvoiceStatus.UPLOADED.value,
    )
    extraction_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    stated_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    computed_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    totals_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InvoiceLine.line_no",
    )


class InvoiceLine(UUIDPrimaryKeyMixin, OrgScopedMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_lang: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(Text, nullable=True)
    pack_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    pack_qty: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    pack_unit: Mapped[PackUnit | None] = mapped_column(
        pg_enum(PackUnit, "pack_unit"), nullable=True
    )
    case_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    unit_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extended_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_credit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    confidence: Mapped[float] = mapped_column(Numeric, nullable=False)
    match_status: Mapped[LineMatchStatus] = mapped_column(
        pg_enum(LineMatchStatus, "line_match_status"),
        nullable=False,
        default=LineMatchStatus.UNMATCHED,
        server_default=LineMatchStatus.UNMATCHED.value,
    )
    matched_ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    match_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_price_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_entries.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
