"""Search endpoint (PR-4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.models.enums import Category, PurchaseFrequency
from app.schemas.search import SearchResponse
from app.services.search import search_ingredients
from app.services.translation import TranslationService, get_translation_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "/ingredients",
    response_model=SearchResponse,
    summary="Search ingredients across languages/spellings",
)
@limiter.limit("60/minute")
async def search(
    request: Request,
    q: str = Query(min_length=1, max_length=100),
    lang: str | None = Query(default=None, max_length=10),
    frequency: PurchaseFrequency | None = Query(default=None),
    category: Category | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
    translation: TranslationService = Depends(get_translation_service),
) -> SearchResponse:
    return await search_ingredients(
        session,
        ctx,
        q=q,
        lang=lang,
        category=category.value if category else None,
        frequency=frequency.value if frequency else None,
        limit=limit,
        translation=translation,
    )
