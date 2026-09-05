"""agent_profiles: operator guardrails text

Revision ID: d8b4f1c2a903
Revises: a4c8e2f91b07
Create Date: 2026-09-04 21:40:00.000000

Nullable: an absent value means no operator extras, same as persona.

|| Texto de guardrails de operador. Null = sin extras, igual que persona.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8b4f1c2a903"
down_revision: Union[str, Sequence[str], None] = "a4c8e2f91b07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("agent_profiles", sa.Column("guardrails", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("agent_profiles", "guardrails")
