"""add refresh_tokens and audit_logs

Revision ID: 84f3e71da89b
Revises: f4f2d2946fec
Create Date: 2026-06-25 08:16:34.652210
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "84f3e71da89b"
down_revision: str | None = "f4f2d2946fec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # refresh_tokens table (for refresh-token auth flow).
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
