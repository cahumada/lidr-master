"""answer_prompts

Revision ID: c7f3a81b46d2
Revises: b6e2f9d41a77
Create Date: 2026-09-11 14:00:00.000000

What was sent to the model, kept for a short window so a bad answer can be
diagnosed against the prompt that produced it. Its own table and not a column on
`llm_usage_events`: that one is accounting, small and permanent, and a 7-day
retention does not belong on it.

|| Lo que se le mandó al modelo, guardado por una ventana corta. Tabla propia y
no una columna de `llm_usage_events`, que es contabilidad permanente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c7f3a81b46d2"
down_revision: str | None = "b6e2f9d41a77"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "answer_prompts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("agent", sa.String(length=48), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=True),
        sa.Column("context_budget", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("system_text", sa.Text(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # The retention sweep walks this on every write.
    # || Por acá barre la retención en cada escritura.
    op.create_index(
        "ix_answer_prompts_tenant_created",
        "answer_prompts",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_answer_prompts_tenant_created", table_name="answer_prompts")
    op.drop_table("answer_prompts")
