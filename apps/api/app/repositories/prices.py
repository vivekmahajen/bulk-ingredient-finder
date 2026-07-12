"""Price-entry repository."""

from __future__ import annotations

from app.models.price import PriceEntry
from app.repositories.base import OrgScopedRepository


class PriceRepository(OrgScopedRepository[PriceEntry]):
    model = PriceEntry
