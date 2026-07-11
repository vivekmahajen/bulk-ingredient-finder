"""ingredient needs_review flag

Adds ``ingredients.needs_review`` — set when auto-translation could not confirm an
English canonical name (provider outage, or the translation equalled the input),
so a human can confirm it later.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ingredients ADD COLUMN needs_review boolean NOT NULL DEFAULT false"
    )
    op.execute("CREATE INDEX ix_ingredients_needs_review ON ingredients (org_id, needs_review)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ingredients_needs_review")
    op.execute("ALTER TABLE ingredients DROP COLUMN IF EXISTS needs_review")
