"""Auth request/response schemas.

Password policy: ≥10 chars (enforced here) and zxcvbn score ≥3 (enforced in the
web UI before submit).
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role

MIN_PASSWORD_LEN = 10


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    locale: str = Field(default="en", min_length=2, max_length=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class MagicLinkRequest(BaseModel):
    email: EmailStr


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=200)


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role: Role = Role.STAFF
    display_name: str | None = Field(default=None, max_length=200)


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    locale: str = Field(default="en", min_length=2, max_length=10)


class OkResponse(BaseModel):
    ok: bool = True
    # Populated only outside production (magic-link / forgot-password), so flows
    # can be exercised in tests/dev without an email provider.
    dev_token: str | None = None


class InviteCreatedResponse(BaseModel):
    """The dev/testing surface returns the token so flows can be exercised without
    an email provider. In production the token is only ever delivered by email."""

    invite_id: str
    email: EmailStr
    role: Role
    token: str | None = None
