"""Ingredient read endpoints (PR-2).

Write flows (add ingredient with translation/aliases) arrive in PR-3; search in
PR-4. This exposes the org-scoped list/detail so the catalog is reachable now.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.repositories.ingredients import IngredientRepository
from app.schemas.ingredient import IngredientRead

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientRead], summary="List active ingredients")
async def list_ingredients(
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[IngredientRead]:
    repo = IngredientRepository(session, ctx.org_id)
    ingredients = await repo.list_with_aliases()
    return [IngredientRead.model_validate(i) for i in ingredients]


@router.get("/{ingredient_id}", response_model=IngredientRead, summary="Get one ingredient")
async def get_ingredient(
    ingredient_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> IngredientRead:
    repo = IngredientRepository(session, ctx.org_id)
    ingredient = await repo.get_with_aliases(ingredient_id)
    if ingredient is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Ingredient not found",
            detail=f"No ingredient {ingredient_id} in this org.",
        )
    return IngredientRead.model_validate(ingredient)
