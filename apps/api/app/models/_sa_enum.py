"""Helper to build Postgres native-enum columns from ``StrEnum`` types.

Ensures the stored values are the enum *values* (e.g. ``"twice_weekly"``) rather
than member names, and pins the Postgres type name for stable migrations.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        create_type=False,  # types are created explicitly in the migration
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
    )
