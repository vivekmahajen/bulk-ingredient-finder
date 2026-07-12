"""Ingredient read endpoints (PR-2).

Write flows (add ingredient with translation/aliases) arrive in PR-3; search in
PR-4. This exposes the org-scoped list/detail so the catalog is reachable now.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.core.limiter import limiter
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.models.enums import AliasKind
from app.models.ingredient import IngredientAlias
from app.repositories.ingredients import IngredientRepository
from app.repositories.tenancy import OrgRepository
from app.schemas.discovery import DiscoverResponse
from app.schemas.ingredient import (
    AliasCreate,
    BulkIngredientCreate,
    BulkIngredientResult,
    BulkIngredientRowResult,
    IngredientAliasRead,
    IngredientCreate,
    IngredientRead,
)
from app.services import audit
from app.services.ingredients import LanguageAmbiguous, add_ingredient
from app.services.price_discovery import DiscoveryQuery, get_discovery_service
from app.services.translation import TranslationService, get_translation_service

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientRead], summary="List active ingredients")
async def list_ingredients(
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> list[IngredientRead]:
    repo = IngredientRepository(session, ctx.org_id)
    ingredients = await repo.list_with_aliases()
    return [IngredientRead.model_validate(i) for i in ingredients]


@router.post(
    "",
    response_model=IngredientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an ingredient (auto-detect/translate/transliterate + synonyms)",
)
@limiter.limit("30/minute")
async def create_ingredient(
    request: Request,
    payload: IngredientCreate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    translation: TranslationService = Depends(get_translation_service),
) -> IngredientRead:
    try:
        ingredient = await add_ingredient(session, ctx, payload, translation)
    except LanguageAmbiguous as exc:
        # 422 with candidate languages so the UI can ask "which language is this?".
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Ambiguous language",
            detail="Could not confidently detect the language. Please choose one.",
            type_="https://rasoi.radar/problems/ambiguous-language",
        ) from exc
    await session.commit()

    full = await IngredientRepository(session, ctx.org_id).get_with_aliases(ingredient.id)
    assert full is not None
    return IngredientRead.model_validate(full)


@router.post(
    "/bulk",
    response_model=BulkIngredientResult,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Bulk-add ingredients (≤100, per-row results)",
)
@limiter.limit("10/minute")
async def create_ingredients_bulk(
    request: Request,
    payload: BulkIngredientCreate,
    response: Response,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    translation: TranslationService = Depends(get_translation_service),
) -> BulkIngredientResult:
    results: list[BulkIngredientRowResult] = []
    created = 0

    for i, item in enumerate(payload.items):
        try:
            # Each row runs in its own savepoint so one bad row can't poison the batch.
            async with session.begin_nested():
                ingredient = await add_ingredient(session, ctx, item, translation)
            results.append(
                BulkIngredientRowResult(
                    index=i,
                    ok=True,
                    id=ingredient.id,
                    canonical_name_en=ingredient.canonical_name_en,
                    needs_review=ingredient.needs_review,
                )
            )
            created += 1
        except LanguageAmbiguous:
            results.append(
                BulkIngredientRowResult(
                    index=i,
                    ok=False,
                    error="Ambiguous language — set a language for this row.",
                )
            )
        except Exception as exc:  # noqa: BLE001 — isolate one bad row from the batch
            results.append(BulkIngredientRowResult(index=i, ok=False, error=str(exc)))

    await session.commit()
    if created == len(payload.items):
        response.status_code = status.HTTP_201_CREATED
    return BulkIngredientResult(
        created=created, failed=len(payload.items) - created, results=results
    )


@router.get(
    "/{ingredient_id}/discover-prices",
    response_model=DiscoverResponse,
    summary="Find bulk sellers + prices on the web (estimated, not verified)",
)
@limiter.limit("6/minute")
async def discover_prices(
    request: Request,
    ingredient_id: uuid.UUID,
    radius_miles: float = Query(default=25, ge=0),
    location: str | None = Query(default=None),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> DiscoverResponse:
    ingredient = await IngredientRepository(session, ctx.org_id).get_with_aliases(ingredient_id)
    if ingredient is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Ingredient not found",
            detail=f"No ingredient {ingredient_id} in this org.",
        )

    name = ingredient.canonical_name_en
    aliases = [a.alias for a in ingredient.aliases if a.alias.lower() != name.lower()][:6]

    loc = location.strip() if location and location.strip() else None
    if loc is None:
        org = await OrgRepository(session).get(ctx.org_id)
        if org and org.home_lat is not None and org.home_lng is not None:
            loc = f"latitude {float(org.home_lat):.4f}, longitude {float(org.home_lng):.4f}"
    query_str = f"{name} bulk wholesale" + (f" near {loc}" if loc else "")

    service = get_discovery_service()
    if service is None:
        return DiscoverResponse(
            configured=False,
            query=query_str,
            notes=[
                "Web price discovery isn't set up yet. Set DISCOVERY_PROVIDER=claude and "
                "ANTHROPIC_API_KEY in the API environment to enable it."
            ],
        )

    sellers, notes = await service.discover(
        DiscoveryQuery(
            ingredient_name=name,
            aliases=aliases,
            location=loc,
            radius_miles=radius_miles or None,
        )
    )
    return DiscoverResponse(configured=True, query=query_str, sellers=sellers, notes=notes)


@router.post(
    "/{ingredient_id}/aliases",
    response_model=IngredientAliasRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user alias (correction)",
)
async def add_alias(
    ingredient_id: uuid.UUID,
    payload: AliasCreate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> IngredientAliasRead:
    repo = IngredientRepository(session, ctx.org_id)
    ingredient = await repo.get(ingredient_id)
    if ingredient is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Ingredient not found",
            detail=f"No ingredient {ingredient_id} in this org.",
        )
    if await repo.alias_exists(ingredient_id, payload.alias.strip(), payload.lang):
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            title="Alias already exists",
            detail=f"'{payload.alias}' ({payload.lang}) is already an alias.",
        )
    alias = IngredientAlias(
        org_id=ctx.org_id,
        ingredient_id=ingredient_id,
        alias=payload.alias.strip(),
        lang=payload.lang,
        kind=AliasKind.USER_ALIAS,
    )
    session.add(alias)
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="alias.create",
        entity="ingredient_alias",
        entity_id=ingredient_id,
        meta={"alias": payload.alias, "lang": payload.lang},
    )
    await session.commit()
    await session.refresh(alias)
    return IngredientAliasRead.model_validate(alias)


@router.delete(
    "/{ingredient_id}/aliases/{alias_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an alias (correction)",
)
async def delete_alias(
    ingredient_id: uuid.UUID,
    alias_id: uuid.UUID,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = IngredientRepository(session, ctx.org_id)
    alias = await repo.get_alias(alias_id)
    if alias is None or alias.ingredient_id != ingredient_id:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Alias not found",
            detail=f"No alias {alias_id} on ingredient {ingredient_id}.",
        )
    await session.delete(alias)
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="alias.delete",
        entity="ingredient_alias",
        entity_id=ingredient_id,
        meta={"alias_id": str(alias_id)},
    )
    await session.commit()


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
