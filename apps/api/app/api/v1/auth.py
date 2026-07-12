"""Authentication endpoints (PR-1). Tokens are delivered as httpOnly cookies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.errors import ProblemException
from app.core.limiter import limiter
from app.db.session import get_session
from app.deps import RequestContext, require_role
from app.models.enums import Role
from app.schemas.auth import (
    InviteAcceptRequest,
    InviteCreatedResponse,
    InviteCreateRequest,
    LoginRequest,
    MagicLinkRequest,
    OkResponse,
    PasswordForgotRequest,
    PasswordResetRequest,
    RegisterRequest,
)
from app.services import auth as auth_service
from app.services.auth import IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])


def _expose_token() -> bool:
    """Return single-use tokens in the response body only outside production, so
    tests / local dev can exercise flows without an email provider."""
    return settings.environment.lower() != "production"


def _apply(response: Response, tokens: IssuedTokens) -> None:
    set_auth_cookies(response, access=tokens.access, refresh=tokens.refresh, csrf=tokens.csrf)


@router.post("/register", response_model=OkResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    tokens = await auth_service.register(
        session,
        org_name=payload.org_name,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        locale=payload.locale,
        multi_tenant=settings.multi_tenant,
    )
    _apply(response, tokens)
    return OkResponse()


@router.post("/login", response_model=OkResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    tokens = await auth_service.login(session, email=payload.email, password=payload.password)
    _apply(response, tokens)
    return OkResponse()


@router.post("/refresh", response_model=OkResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="No refresh token",
            detail="Sign in again.",
        )
    tokens = await auth_service.refresh(session, refresh_token=token)
    _apply(response, tokens)
    return OkResponse()


@router.post("/logout", response_model=OkResponse)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    await auth_service.logout(session, refresh_token=request.cookies.get(REFRESH_COOKIE))
    clear_auth_cookies(response)
    return OkResponse()


@router.post("/magic-link", response_model=OkResponse)
@limiter.limit("5/minute")
async def magic_link(
    request: Request,
    payload: MagicLinkRequest,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    token = await auth_service.create_magic_link(session, email=payload.email)
    await session.commit()
    # Uniform response regardless of whether the email exists.
    return OkResponse(dev_token=token if _expose_token() else None)


@router.get("/magic/callback", response_model=OkResponse)
async def magic_callback(
    token: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    tokens = await auth_service.consume_magic_link(session, token=token)
    _apply(response, tokens)
    return OkResponse()


@router.post("/password/forgot", response_model=OkResponse)
@limiter.limit("5/minute")
async def password_forgot(
    request: Request,
    payload: PasswordForgotRequest,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    token = await auth_service.create_password_reset(session, email=payload.email)
    await session.commit()
    return OkResponse(dev_token=token if _expose_token() else None)


@router.post("/password/reset", response_model=OkResponse)
async def password_reset(
    payload: PasswordResetRequest,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    await auth_service.reset_password(session, token=payload.token, password=payload.password)
    return OkResponse()


@router.post("/invites", response_model=InviteCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreateRequest,
    ctx: RequestContext = Depends(require_role(Role.OWNER, Role.MANAGER)),
    session: AsyncSession = Depends(get_session),
) -> InviteCreatedResponse:
    user, token = await auth_service.create_invite(
        session,
        org_id=ctx.org_id,
        inviter_id=ctx.user_id,
        email=payload.email,
        role=payload.role,
        display_name=payload.display_name,
    )
    return InviteCreatedResponse(
        invite_id=str(user.id),
        email=payload.email,
        role=payload.role,
        token=token if _expose_token() else None,
    )


@router.post("/invites/accept", response_model=OkResponse)
async def accept_invite(
    payload: InviteAcceptRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> OkResponse:
    tokens = await auth_service.accept_invite(
        session,
        token=payload.token,
        password=payload.password,
        display_name=payload.display_name,
        locale=payload.locale,
    )
    _apply(response, tokens)
    return OkResponse()
