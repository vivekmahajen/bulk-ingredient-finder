"""enable postgres extensions

Enables the PostgreSQL extensions the domain model relies on:
  - pg_trgm       trigram similarity for fuzzy ingredient search
  - unaccent      accent-insensitive matching across languages
  - cube          n-dimensional cube type (dependency of earthdistance)
  - earthdistance great-circle distance for nearest-store search

Revision ID: 0001
Revises:
Create Date: 2026-07-11 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ("pg_trgm", "unaccent", "cube", "earthdistance")


def upgrade() -> None:
    for ext in EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')


def downgrade() -> None:
    # Drop in reverse so earthdistance goes before its cube dependency.
    for ext in reversed(EXTENSIONS):
        op.execute(f'DROP EXTENSION IF EXISTS "{ext}"')
