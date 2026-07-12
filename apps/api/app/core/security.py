"""Security primitives: Argon2id password hashing, JWT access tokens, opaque
refresh/magic/verify/reset tokens.

Refresh and single-use tokens are opaque random strings; only their SHA-256
*hash* is persisted (``auth_tokens.token_hash``). Access tokens are short-lived
JWTs signed with ``JWT_SECRET``.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
MAGIC_TTL = timedelta(minutes=15)
RESET_TTL = timedelta(hours=1)
VERIFY_TTL = timedelta(days=3)

_ALGO = "HS256"
_hasher = PasswordHasher()  # Argon2id defaults


# --- Passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-time verify. Always runs a hash even when there's no stored hash
    (dummy verify) so timing doesn't leak whether the account exists."""
    if not password_hash:
        # Spend comparable time to a real verify to resist user enumeration.
        try:
            _hasher.verify(_DUMMY_HASH, password)
        except VerifyMismatchError:
            pass
        return False
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


_DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time")


# --- Opaque tokens (refresh / magic / verify / reset) ------------------------


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


# --- Access JWT --------------------------------------------------------------


def create_access_token(*, user_id: uuid.UUID, org_id: uuid.UUID, role: str) -> str:
    now = now_utc()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + ACCESS_TTL).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on invalid/expired tokens."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])


# --- CSRF --------------------------------------------------------------------


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
