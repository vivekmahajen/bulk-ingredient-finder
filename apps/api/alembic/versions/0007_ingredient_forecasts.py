"""ingredient forecasts (optional monthly demand + sourcing)

Adds ``ingredient_forecasts`` — a 1:1, all-nullable companion to ``ingredients``
holding optional monthly demand (jan..dec), annual total, per-serving size, and
the recommended vendor + website. Only an ingredient's name is required; this
table captures the rich forecast data when a user has it.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-12 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ingredient_forecasts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
            "jan" numeric,
            "feb" numeric,
            "mar" numeric,
            "apr" numeric,
            "may" numeric,
            "jun" numeric,
            "jul" numeric,
            "aug" numeric,
            "sep" numeric,
            "oct" numeric,
            "nov" numeric,
            "dec" numeric,
            annual numeric,
            g_ml_per_serving numeric,
            recommended_vendor text,
            vendor_website text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_forecast_ingredient UNIQUE (ingredient_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_ingredient_forecasts_org_id ON ingredient_forecasts(org_id)")
    op.execute(
        "CREATE INDEX ix_ingredient_forecasts_ingredient_id "
        "ON ingredient_forecasts(ingredient_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE ingredient_forecasts")
