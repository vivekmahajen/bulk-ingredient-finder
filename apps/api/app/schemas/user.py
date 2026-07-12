"""User / me schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Role

SUPPORTED_LOCALES = {"en", "hi", "es", "zh", "vi", "ko", "pt"}


class OrgBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class MeRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    locale: str
    role: Role
    org: OrgBrief


class LocaleUpdate(BaseModel):
    locale: str = Field(min_length=2, max_length=10)


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    locale: str = Field(default="en", min_length=2, max_length=10)
