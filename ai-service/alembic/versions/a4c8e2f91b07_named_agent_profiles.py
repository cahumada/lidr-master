"""named agent profiles: id, name, is_default

Revision ID: a4c8e2f91b07
Revises: ec7c1a188b48
Create Date: 2026-09-04 13:30:00.000000

An existing anonymous row (PK = agent_key) is copied to a default profile
named ``Default``. An agent with no row does not receive an invented one.

|| Una fila anónima existente (PK = agent_key) se copia a un perfil default
llamado ``Default``. Un agente sin fila no recibe una inventada.
"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "a4c8e2f91b07"
down_revision: Union[str, Sequence[str], None] = "ec7c1a188b48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("agent_profiles", sa.Column("id", sa.String(length=36), nullable=True))
    op.add_column("agent_profiles", sa.Column("name", sa.String(length=64), nullable=True))
    op.add_column("agent_profiles", sa.Column("is_default", sa.Boolean(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT agent_key FROM agent_profiles")).fetchall()
    for (agent_key,) in rows:
        bind.execute(
            sa.text(
                "UPDATE agent_profiles SET id = :id, name = 'Default', is_default = true "
                "WHERE agent_key = :agent_key"
            ),
            {"id": str(uuid4()), "agent_key": agent_key},
        )

    op.alter_column("agent_profiles", "id", existing_type=sa.String(length=36), nullable=False)
    op.alter_column("agent_profiles", "name", existing_type=sa.String(length=64), nullable=False)
    op.alter_column(
        "agent_profiles",
        "is_default",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )
    op.drop_constraint("agent_profiles_pkey", "agent_profiles", type_="primary")
    op.create_primary_key("agent_profiles_pkey", "agent_profiles", ["id"])
    op.create_index(
        "uq_agent_profiles_agent_key_name",
        "agent_profiles",
        ["agent_key", sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema — keeps one row per agent (the default, or the first).

    || Baja el esquema: deja una fila por agente (el default, o la primera).
    """
    bind = op.get_bind()
    extras = bind.execute(
        sa.text(
            "SELECT id FROM agent_profiles WHERE is_default IS NOT TRUE "
            "OR id NOT IN ("
            "  SELECT DISTINCT ON (agent_key) id FROM agent_profiles "
            "  ORDER BY agent_key, is_default DESC, updated_at DESC"
            ")"
        )
    ).fetchall()
    for (profile_id,) in extras:
        bind.execute(
            sa.text("DELETE FROM agent_profiles WHERE id = :id"),
            {"id": profile_id},
        )

    op.drop_index("uq_agent_profiles_agent_key_name", table_name="agent_profiles")
    op.drop_constraint("agent_profiles_pkey", "agent_profiles", type_="primary")
    op.drop_column("agent_profiles", "is_default")
    op.drop_column("agent_profiles", "name")
    op.drop_column("agent_profiles", "id")
    op.create_primary_key("agent_profiles_pkey", "agent_profiles", ["agent_key"])
