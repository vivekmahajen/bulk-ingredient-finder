"""Auth cookie helpers.

Access + refresh tokens live in httpOnly, Secure, SameSite=Lax cookies (never in
localStorage). The CSRF token is a non-httpOnly cookie so the SPA can echo it in an
``X-CSRF-Token`` header (double-submit pattern) on mutating requests.
"""

from __future__ import annotations

from fastapi import Response

from app.core.config import settings
from app.core.security import ACCESS_TTL, REFRESH_TTL

ACCESS_COOKIE = "rr_access"
REFRESH_COOKIE = "rr_refresh"
CSRF_COOKIE = "rr_csrf"
CSRF_HEADER = "X-CSRF-Token"


# Environments served over plain http (no TLS), where Secure cookies would be
# silently dropped by the browser/client. Everything else (production, staging,
# preview deploys, and any unknown environment) defaults to Secure.
_INSECURE_TRANSPORT_ENVS = frozenset({"development", "test", "ci"})


def _secure() -> bool:
    return settings.environment.lower() not in _INSECURE_TRANSPORT_ENVS


def set_auth_cookies(response: Response, *, access: str, refresh: str, csrf: str) -> None:
    secure = _secure()
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=int(ACCESS_TTL.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")
