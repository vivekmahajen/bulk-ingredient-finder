"""org home location

Adds ``orgs.home_lat`` / ``orgs.home_lng`` — the restaurant's own location, used
to compute store distances for radius-aware search (PR-5) and compare (PR-7).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE orgs ADD COLUMN home_lat numeric")
    op.execute("ALTER TABLE orgs ADD COLUMN home_lng numeric")


def downgrade() -> None:
    op.execute("ALTER TABLE orgs DROP COLUMN IF EXISTS home_lng")
    op.execute("ALTER TABLE orgs DROP COLUMN IF EXISTS home_lat")
