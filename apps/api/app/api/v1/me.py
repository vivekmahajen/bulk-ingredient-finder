"""Current-user endpoints (PR-8): /me and locale persistence for the switcher."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.db.session import get_session
from app.deps import RequestContext, get_context
from app.repositories.tenancy import OrgRepository, UserRepository
from app.schemas.user import SUPPORTED_LOCALES, LocaleUpdate, MeRead, OrgBrief
from app.services import audit

router = APIRouter(prefix="/me", tags=["me"])


async def _me(session: AsyncSession, ctx: RequestContext) -> MeRead:
    org = await OrgRepository(session).get(ctx.org_id)
    user = await UserRepository(session).get(ctx.user_id) if ctx.user_id else None
    if org is None or user is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="No current user",
            detail="No user/org resolved for this request.",
        )
    return MeRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        role=user.role,
        org=OrgBrief.model_validate(org),
    )


@router.get("", response_model=MeRead, summary="Current user + org + role + locale")
async def get_me(
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> MeRead:
    return await _me(session, ctx)


@router.patch("/locale", response_model=MeRead, summary="Set the current user's locale")
async def set_locale(
    payload: LocaleUpdate,
    ctx: RequestContext = Depends(get_context),
    session: AsyncSession = Depends(get_session),
) -> MeRead:
    if payload.locale not in SUPPORTED_LOCALES:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Unsupported locale",
            detail=f"locale must be one of {sorted(SUPPORTED_LOCALES)}",
        )
    user = await UserRepository(session).get(ctx.user_id) if ctx.user_id else None
    if user is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND, title="No current user", detail="unknown user"
        )
    user.locale = payload.locale
    audit.record(
        session,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        action="user.locale",
        entity="user",
        entity_id=user.id,
        meta={"locale": payload.locale},
    )
    await session.commit()
    return await _me(session, ctx)
