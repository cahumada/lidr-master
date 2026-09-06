"""conversation_sessions: memoria de la conversación entre turnos

Revision ID: f3a7c21e9b40
Revises: d8b4f1c2a903
Create Date: 2026-09-05 09:40:00.000000

Una fila por conversación. `facts`, `anchors` y `turns` son JSONB y no
columnas —al revés que en `chunks`, y por la misma razón— porque son listas
anidadas de largo variable y nunca se consulta adentro: una sesión se lee
entera, por id.

El índice sobre `updated_at` es para el barrido por TTL, que es la única
consulta que NO va por clave primaria.

|| One row per conversation. `facts`, `anchors` and `turns` are JSONB rather
than columns -- the opposite call from `chunks`, for the same reason -- because
they are variable-length nested lists nothing ever queries inside: a session is
read whole, by id. The index on `updated_at` serves the TTL sweep, the only
query that does NOT go by primary key.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a7c21e9b40"
down_revision: str | None = "d8b4f1c2a903"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "facts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "anchors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "turns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_sessions_updated_at",
        "conversation_sessions",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_sessions_updated_at", table_name="conversation_sessions"
    )
    op.drop_table("conversation_sessions")
