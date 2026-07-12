"""Org-scoped invoice repository. All invoice DB access lives here."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.ingredient import Ingredient
from app.models.invoice import Invoice, InvoiceLine
from app.models.price import PriceEntry
from app.models.store import Store
from app.repositories.base import OrgScopedRepository


class InvoiceRepository(OrgScopedRepository[Invoice]):
    model = Invoice

    async def get_with_lines(self, invoice_id: uuid.UUID) -> Invoice | None:
        result = await self.session.execute(
            self.scoped().where(Invoice.id == invoice_id).options(selectinload(Invoice.lines))
        )
        return result.scalar_one_or_none()

    async def get_by_sha(self, image_sha256: str) -> Invoice | None:
        result = await self.session.execute(
            self.scoped().where(Invoice.image_sha256 == image_sha256)
        )
        return result.scalar_one_or_none()

    async def get_line(self, line_id: uuid.UUID) -> InvoiceLine | None:
        result = await self.session.execute(
            select(InvoiceLine).where(
                InvoiceLine.org_id == self.org_id, InvoiceLine.id == line_id
            )
        )
        return result.scalar_one_or_none()

    async def line_count(self, invoice_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(InvoiceLine.id)).where(
                InvoiceLine.org_id == self.org_id, InvoiceLine.invoice_id == invoice_id
            )
        )
        return int(result.scalar_one())

    async def list_page(
        self, *, status: str | None, page: int, page_size: int
    ) -> tuple[list[tuple[Invoice, int]], int]:
        base = self.scoped()
        if status:
            base = base.where(Invoice.status == status)

        total_res = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = int(total_res.scalar_one())

        line_count = (
            select(InvoiceLine.invoice_id, func.count(InvoiceLine.id).label("n"))
            .where(InvoiceLine.org_id == self.org_id)
            .group_by(InvoiceLine.invoice_id)
            .subquery()
        )
        stmt = (
            base.add_columns(func.coalesce(line_count.c.n, 0))
            .outerjoin(line_count, line_count.c.invoice_id == Invoice.id)
            .order_by(Invoice.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(row[0], int(row[1])) for row in rows], total

    async def count_created_today(self) -> int:
        start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        result = await self.session.execute(
            select(func.count()).where(
                Invoice.org_id == self.org_id, Invoice.created_at >= start
            )
        )
        return int(result.scalar_one())

    async def hint_store_names(self, limit: int = 50) -> list[str]:
        result = await self.session.execute(
            select(Store.name).where(Store.org_id == self.org_id).limit(limit)
        )
        return [str(n) for n in result.scalars().all()]

    async def hint_ingredient_names(self, limit: int = 100) -> list[str]:
        result = await self.session.execute(
            select(Ingredient.canonical_name_en)
            .where(Ingredient.org_id == self.org_id, Ingredient.is_active.is_(True))
            .order_by(Ingredient.created_at.desc())
            .limit(limit)
        )
        return [str(n) for n in result.scalars().all()]

    async def price_entry_exists(
        self,
        *,
        ingredient_id: uuid.UUID,
        store_id: uuid.UUID,
        observed_at: date,
        price_cents: int,
    ) -> bool:
        result = await self.session.execute(
            select(PriceEntry.id).where(
                PriceEntry.org_id == self.org_id,
                PriceEntry.ingredient_id == ingredient_id,
                PriceEntry.store_id == store_id,
                PriceEntry.observed_at == observed_at,
                PriceEntry.price_cents == price_cents,
            )
        )
        return result.first() is not None
