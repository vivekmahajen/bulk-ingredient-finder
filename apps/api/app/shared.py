"""Python (Pydantic) mirror of ``packages/shared`` cross-language constants.

The canonical values live in ``packages/shared/schema.json``. The TypeScript (zod)
mirror is ``packages/shared/src/index.ts``. Keep all three in sync.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

APP_NAME = "Rasoi Radar"
API_VERSION = "api/v1"


class Locale(StrEnum):
    EN = "en"
    HI = "hi"
    ES = "es"
    ZH = "zh"
    VI = "vi"
    KO = "ko"
    PT = "pt"


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class Problem(BaseModel):
    """RFC-7807 problem+json envelope."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
