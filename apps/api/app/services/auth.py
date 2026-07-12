"""Authentication flows: register, login, refresh rotation, magic-link, invites,
password reset — with lockout and refresh-reuse detection.

Token material is returned to the caller (the endpoint layer sets the httpOnly
cookies). Email-bearing flows (magic-link, forgot-password) respond uniformly
whether or not the address exists, to resist account enumeration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.errors import ProblemException
from app.models.enums import AuthTokenKind, Role
from app.models.org import Org
from app.models.user import User
from app.repositories.auth import AuthTokenRepository
from app.repositories.tenancy import UserRepository
from app.services import audit

MAX_FAILED_LOGINS = 10
LOCKOUT = timedelta(minutes=15)


@dataclass
class IssuedTokens:
    user: User
    access: str
    refresh: str
    csrf: str


def _issue(
    session: AsyncSession, user: User, *, family_id: uuid.UUID | None = None
) -> IssuedTokens:
    """Mint an access JWT + a rotating refresh token (persisted as a hash)."""
    now = security.now_utc()
    access = security.create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
    refresh_plain = security.generate_token()
    family = family_id or uuid.uuid4()
    AuthTokenRepository(session).add(
        user_id=user.id,
        kind=AuthTokenKind.REFRESH,
        token_hash=security.hash_token(refresh_plain),
        expires_at=now + security.REFRESH_TTL,
        family_id=family,
    )
    return IssuedTokens(
        user=user, access=access, refresh=refresh_plain, csrf=security.generate_csrf_token()
    )


async def register(
    session: AsyncSession,
    *,
    org_name: str,
    email: str,
    password: str,
    display_name: str,
    locale: str,
    multi_tenant: bool,
) -> IssuedTokens:
    if not multi_tenant:
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Registration disabled",
            detail="Self-registration is off in dogfood mode; you must be invited.",
        )
    users = UserRepository(session)
    if await users.get_by_email(email) is not None:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT, title="Email already registered", detail=email
        )
    org = Org(name=org_name)
    session.add(org)
    await session.flush()
    user = User(
        org_id=org.id,
        email=email,
        password_hash=security.hash_password(password),
        display_name=display_name,
        locale=locale,
        role=Role.OWNER,
    )
    session.add(user)
    await session.flush()
    tokens = _issue(session, user)
    audit.record(
        session,
        org_id=org.id,
        user_id=user.id,
        action="auth.register",
        entity="user",
        entity_id=user.id,
        meta={},
    )
    await session.commit()
    return tokens


async def login(session: AsyncSession, *, email: str, password: str) -> IssuedTokens:
    users = UserRepository(session)
    user = await users.get_by_email(email)
    now = security.now_utc()

    if user is not None and user.locked_until is not None and user.locked_until > now:
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Account locked",
            detail="Too many failed attempts. Try again later.",
        )

    # Constant-time verify (dummy hash when the user/hash is absent).
    ok = security.verify_password(user.password_hash if user else None, password)
    if not ok or user is None or not user.is_active:
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + LOCKOUT
            audit.record(
                session,
                org_id=user.org_id,
                user_id=user.id,
                action="auth.login_failed",
                entity="user",
                entity_id=user.id,
                meta={"count": user.failed_login_count},
            )
            await session.commit()
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Invalid credentials",
            detail="Email or password is incorrect.",
        )

    user.failed_login_count = 0
    user.locked_until = None
    tokens = _issue(session, user)
    audit.record(
        session,
        org_id=user.org_id,
        user_id=user.id,
        action="auth.login",
        entity="user",
        entity_id=user.id,
        meta={},
    )
    await session.commit()
    return tokens


async def refresh(session: AsyncSession, *, refresh_token: str) -> IssuedTokens:
    repo = AuthTokenRepository(session)
    now = security.now_utc()
    token = await repo.get_by_hash(security.hash_token(refresh_token), AuthTokenKind.REFRESH)
    if token is None:
        raise _invalid_refresh()

    # Reuse detection: a refresh token presented twice burns the whole family.
    if token.used_at is not None:
        if token.family_id is not None:
            await repo.revoke_family(token.family_id, now)
        await session.commit()
        raise _invalid_refresh()

    if token.expires_at <= now:
        raise _invalid_refresh()

    await repo.mark_used(token, now)
    users = UserRepository(session)
    user = await users.get(token.user_id)
    if user is None or not user.is_active:
        raise _invalid_refresh()
    tokens = _issue(session, user, family_id=token.family_id)
    await session.commit()
    return tokens


async def logout(session: AsyncSession, *, refresh_token: str | None) -> None:
    if refresh_token:
        repo = AuthTokenRepository(session)
        token = await repo.get_by_hash(security.hash_token(refresh_token), AuthTokenKind.REFRESH)
        now = security.now_utc()
        if token is not None:
            await repo.mark_used(token, now)
            if token.family_id is not None:
                await repo.revoke_family(token.family_id, now)
            user = await UserRepository(session).get(token.user_id)
            if user is not None:
                audit.record(
                    session,
                    org_id=user.org_id,
                    user_id=user.id,
                    action="auth.logout",
                    entity="user",
                    entity_id=user.id,
                    meta={},
                )
    await session.commit()


async def create_magic_link(session: AsyncSession, *, email: str) -> str | None:
    """Returns the token (for email delivery) if the user exists, else None.
    The endpoint responds identically either way."""
    user = await UserRepository(session).get_by_email(email)
    if user is None or not user.is_active:
        return None
    return _single_use_token(session, user, AuthTokenKind.MAGIC, security.MAGIC_TTL)


async def consume_magic_link(session: AsyncSession, *, token: str) -> IssuedTokens:
    user = await _consume(session, token, AuthTokenKind.MAGIC)
    tokens = _issue(session, user)
    audit.record(
        session,
        org_id=user.org_id,
        user_id=user.id,
        action="auth.magic_login",
        entity="user",
        entity_id=user.id,
        meta={},
    )
    await session.commit()
    return tokens


async def create_password_reset(session: AsyncSession, *, email: str) -> str | None:
    user = await UserRepository(session).get_by_email(email)
    if user is None or not user.is_active:
        return None
    return _single_use_token(session, user, AuthTokenKind.RESET, security.RESET_TTL)


async def reset_password(session: AsyncSession, *, token: str, password: str) -> None:
    user = await _consume(session, token, AuthTokenKind.RESET)
    user.password_hash = security.hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    # Force re-login everywhere by revoking outstanding refresh tokens.
    await AuthTokenRepository(session).revoke_all_for_user(
        user.id, AuthTokenKind.REFRESH, security.now_utc()
    )
    audit.record(
        session,
        org_id=user.org_id,
        user_id=user.id,
        action="auth.password_reset",
        entity="user",
        entity_id=user.id,
        meta={},
    )
    await session.commit()


async def create_invite(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    inviter_id: uuid.UUID | None,
    email: str,
    role: Role,
    display_name: str | None,
) -> tuple[User, str]:
    users = UserRepository(session)
    existing = await users.get_by_email(email)
    if existing is not None:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT, title="Email already registered", detail=email
        )
    # Placeholder inactive user carries the org + role until the invite is accepted.
    user = User(
        org_id=org_id, email=email, display_name=display_name or email, role=role, is_active=False
    )
    session.add(user)
    await session.flush()
    token = _single_use_token(session, user, AuthTokenKind.VERIFY, security.VERIFY_TTL)
    audit.record(
        session,
        org_id=org_id,
        user_id=inviter_id,
        action="auth.invite",
        entity="user",
        entity_id=user.id,
        meta={"email": email, "role": role.value},
    )
    await session.commit()
    return user, token


async def accept_invite(
    session: AsyncSession, *, token: str, password: str, display_name: str, locale: str
) -> IssuedTokens:
    user = await _consume(session, token, AuthTokenKind.VERIFY)
    user.password_hash = security.hash_password(password)
    user.display_name = display_name
    user.locale = locale
    user.is_active = True
    tokens = _issue(session, user)
    audit.record(
        session,
        org_id=user.org_id,
        user_id=user.id,
        action="auth.invite_accept",
        entity="user",
        entity_id=user.id,
        meta={},
    )
    await session.commit()
    return tokens


# --- helpers -----------------------------------------------------------------


def _single_use_token(
    session: AsyncSession, user: User, kind: AuthTokenKind, ttl: timedelta
) -> str:
    plain = security.generate_token()
    AuthTokenRepository(session).add(
        user_id=user.id,
        kind=kind,
        token_hash=security.hash_token(plain),
        expires_at=security.now_utc() + ttl,
    )
    return plain


async def _consume(session: AsyncSession, token: str, kind: AuthTokenKind) -> User:
    repo = AuthTokenRepository(session)
    now = security.now_utc()
    row = await repo.get_by_hash(security.hash_token(token), kind)
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Invalid or expired token",
            detail="This link is invalid, already used, or expired.",
        )
    await repo.mark_used(row, now)
    user = await UserRepository(session).get(row.user_id)
    if user is None:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST, title="Invalid token", detail="Unknown user."
        )
    return user


def _invalid_refresh() -> ProblemException:
    return ProblemException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        title="Invalid refresh token",
        detail="Please sign in again.",
    )
