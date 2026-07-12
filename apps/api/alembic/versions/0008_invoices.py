"""Invoice capture: invoices + invoice_lines, price provenance, contribute flag.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE invoice_status AS ENUM "
        "('uploaded', 'extracting', 'needs_review', 'committed', 'failed', 'rejected')"
    )
    op.execute(
        "CREATE TYPE line_match_status AS ENUM "
        "('auto_matched', 'suggested', 'unmatched', 'manual', 'excluded')"
    )

    op.execute(
        """
        CREATE TABLE invoices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
            store_id uuid REFERENCES stores(id) ON DELETE SET NULL,
            vendor_name_raw text,
            invoice_number text,
            invoice_date date,
            currency char(3) NOT NULL DEFAULT 'USD',
            image_ref text NOT NULL,
            image_sha256 char(64) NOT NULL,
            page_count int NOT NULL DEFAULT 1,
            status invoice_status NOT NULL DEFAULT 'uploaded',
            extraction_model text,
            extraction_ms int,
            extraction_error text,
            stated_total_cents int,
            computed_total_cents int,
            totals_match boolean,
            created_at timestamptz NOT NULL DEFAULT now(),
            committed_at timestamptz,
            CONSTRAINT uq_invoice_org_sha256 UNIQUE (org_id, image_sha256)
        )
        """
    )
    op.execute("CREATE INDEX ix_invoices_org_id ON invoices(org_id)")
    op.execute("CREATE INDEX ix_invoices_store_id ON invoices(store_id)")
    op.execute("CREATE INDEX ix_invoices_org_status ON invoices(org_id, status)")

    op.execute(
        """
        CREATE TABLE invoice_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
            invoice_id uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            line_no int NOT NULL,
            raw_text text NOT NULL,
            raw_lang text,
            description_en text,
            brand text,
            pack_desc text,
            pack_qty numeric,
            pack_unit pack_unit,
            case_count int,
            unit_price_cents int,
            extended_cents int,
            is_credit boolean NOT NULL DEFAULT false,
            confidence numeric NOT NULL,
            match_status line_match_status NOT NULL DEFAULT 'unmatched',
            matched_ingredient_id uuid REFERENCES ingredients(id) ON DELETE SET NULL,
            match_score numeric,
            created_price_entry_id uuid REFERENCES price_entries(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_invoice_lines_org_id ON invoice_lines(org_id)")
    op.execute("CREATE INDEX ix_invoice_lines_invoice_id ON invoice_lines(invoice_id)")

    op.execute(
        "ALTER TABLE price_entries ADD COLUMN invoice_line_id uuid "
        "REFERENCES invoice_lines(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE orgs ADD COLUMN contribute_prices boolean NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE orgs DROP COLUMN IF EXISTS contribute_prices")
    op.execute("ALTER TABLE price_entries DROP COLUMN IF EXISTS invoice_line_id")
    op.execute("DROP TABLE IF EXISTS invoice_lines")
    op.execute("DROP TABLE IF EXISTS invoices")
    op.execute("DROP TYPE IF EXISTS line_match_status")
    op.execute("DROP TYPE IF EXISTS invoice_status")
