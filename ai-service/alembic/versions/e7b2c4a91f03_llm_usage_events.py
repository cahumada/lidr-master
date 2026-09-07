"""llm_usage_events: one row per billed chat completion

Revision ID: e7b2c4a91f03
Revises: c4e8a91b07d2
Create Date: 2026-09-07 15:00:00.000000

Ledger of provider-reported token usage. Written at complete() time, not
when the conversation turn closes: a human-review reject still cost tokens.

|| Ledger del usage que reportó el proveedor. Se escribe en el complete(),
no al cerrar el turno: un reject del gate humano igual se pagó.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e7b2c4a91f03"
down_revision: str | None = "c4e8a91b07d2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("reported", sa.Boolean(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("thread_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_usage_events_tenant_created",
        "llm_usage_events",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_llm_usage_events_session_id",
        "llm_usage_events",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_events_session_id", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_tenant_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
