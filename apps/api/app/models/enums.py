"""Domain enums, shared by ORM models and Pydantic schemas.

The Postgres native enum ``name`` is pinned explicitly so migrations and models
agree on the type name.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class Category(StrEnum):
    PROTEIN = "protein"
    DAIRY = "dairy"
    PRODUCE = "produce"
    STAPLE = "staple"
    SPICE = "spice"
    FROZEN = "frozen"
    BEVERAGE = "beverage"
    PACKAGING = "packaging"
    OTHER = "other"


class DefaultUnit(StrEnum):
    KG = "kg"
    G = "g"
    L = "l"
    ML = "ml"
    EACH = "each"
    CASE = "case"
    BAG = "bag"


class PurchaseFrequency(StrEnum):
    DAILY = "daily"
    TWICE_WEEKLY = "twice_weekly"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class AliasKind(StrEnum):
    TRANSLATION = "translation"
    TRANSLITERATION = "transliteration"
    SYNONYM = "synonym"
    USER_ALIAS = "user_alias"


class StoreKind(StrEnum):
    BROADLINE = "broadline"
    CASH_AND_CARRY = "cash_and_carry"
    ETHNIC_WHOLESALE = "ethnic_wholesale"
    PRODUCE_HOUSE = "produce_house"
    RETAIL = "retail"
    ONLINE = "online"


class PackUnit(StrEnum):
    KG = "kg"
    G = "g"
    LB = "lb"
    OZ = "oz"
    L = "l"
    ML = "ml"
    GAL = "gal"
    EACH = "each"


class PriceSource(StrEnum):
    INVOICE = "invoice"
    SHELF = "shelf"
    QUOTE = "quote"
    WEBSITE = "website"
    MANUAL = "manual"
