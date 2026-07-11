"""Ingredient + alias repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.ingredient import Ingredient, IngredientAlias
from app.repositories.base import OrgScopedRepository


class IngredientRepository(OrgScopedRepository[Ingredient]):
    model = Ingredient

    async def get_with_aliases(self, ingredient_id: uuid.UUID) -> Ingredient | None:
        stmt = (
            self.scoped()
            .where(Ingredient.id == ingredient_id)
            .options(selectinload(Ingredient.aliases))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_aliases(self) -> list[Ingredient]:
        stmt = (
            self.scoped()
            .where(Ingredient.is_active.is_(True))
            .options(selectinload(Ingredient.aliases))
            .order_by(Ingredient.canonical_name_en)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def alias_exists(self, ingredient_id: uuid.UUID, alias: str, lang: str) -> bool:
        stmt = (
            select(IngredientAlias.id)
            .where(IngredientAlias.org_id == self.org_id)
            .where(IngredientAlias.ingredient_id == ingredient_id)
            .where(IngredientAlias.alias == alias)
            .where(IngredientAlias.lang == lang)
        )
        result = await self.session.execute(stmt)
        return result.first() is not None
