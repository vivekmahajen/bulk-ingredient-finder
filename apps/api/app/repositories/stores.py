"""Store repository."""

from __future__ import annotations

from app.models.store import Store
from app.repositories.base import OrgScopedRepository


class StoreRepository(OrgScopedRepository[Store]):
    model = Store

    async def get_by_name(self, name: str) -> Store | None:
        result = await self.session.execute(self.scoped().where(Store.name == name))
        return result.scalar_one_or_none()
