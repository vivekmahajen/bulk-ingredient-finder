"""translation cache

Caches translation results so we never pay for the same (text, source, target)
twice. Unique on the triple.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE translation_cache (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_text text NOT NULL,
            source_lang varchar(10) NOT NULL,
            target_lang varchar(10) NOT NULL,
            result text NOT NULL,
            romanization text,
            provider text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_translation_cache UNIQUE (source_text, source_lang, target_lang)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS translation_cache")
