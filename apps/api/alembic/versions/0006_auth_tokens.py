"""auth tokens + user lockout

Adds the auth substrate for PR-1:
  * ``auth_tokens`` — only SHA-256 *hashes* of refresh/magic/verify/reset tokens
    are stored; ``family_id`` ties a refresh-token rotation chain together so a
    reuse can revoke the whole family.
  * ``users.failed_login_count`` / ``users.locked_until`` — lockout after too many
    failed logins.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE auth_token_kind AS ENUM ('refresh', 'magic', 'verify', 'reset')"
    )
    op.execute(
        """
        CREATE TABLE auth_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind auth_token_kind NOT NULL,
            token_hash text NOT NULL,
            family_id uuid,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_auth_tokens_token_hash ON auth_tokens(token_hash)")
    op.execute("CREATE INDEX ix_auth_tokens_user_id ON auth_tokens(user_id)")
    op.execute("CREATE INDEX ix_auth_tokens_family_id ON auth_tokens(family_id)")

    op.execute(
        "ALTER TABLE users ADD COLUMN failed_login_count integer NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE users ADD COLUMN locked_until timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS locked_until")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS failed_login_count")
    op.execute("DROP TABLE IF EXISTS auth_tokens")
    op.execute("DROP TYPE IF EXISTS auth_token_kind")
