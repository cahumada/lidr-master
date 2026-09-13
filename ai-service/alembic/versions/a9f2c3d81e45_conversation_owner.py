"""conversation_owner

Revision ID: a9f2c3d81e45
Revises: c7f3a81b46d2
Create Date: 2026-09-12 10:00:00.000000

Who a conversation belongs to. Until now `conversation_sessions` had no owner
column at all — not per user, not per tenant — so every person logged into the
console listed, reopened, renamed and deleted everybody else's.

Nullable on purpose: the rows that already exist have no owner, and inventing
one for them would be worse than leaving them without. With the store's rule
(absence of identity is its own bucket, never a wildcard) they end up invisible
in the console and intact in the database, until `backfill_conversation_owner.py`
assigns them.

|| De quién es una conversación. Hasta ahora `conversation_sessions` no tenía
ninguna columna de dueño —ni por usuario ni por tenant—, así que cualquiera
logueado en la consola listaba, reabría, renombraba y borraba las de todos.
Nullable a propósito: inventarle un dueño a lo que ya existe es peor que
dejarlo sin dueño.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a9f2c3d81e45"
down_revision: str | None = "c7f3a81b46d2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_sessions",
        sa.Column("owner_id", sa.String(length=64), nullable=True),
    )
    # Composite, and `updated_at DESC` because that is the order every listing
    # asks for inside one owner. A lone index on `owner_id` would cover a
    # prefix of this one and earn nothing.
    # || Compuesto, y `updated_at DESC` porque es el orden que pide todo
    # listado adentro de un dueño.
    op.create_index(
        "ix_conversation_sessions_owner_updated",
        "conversation_sessions",
        ["owner_id", sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_sessions_owner_updated", table_name="conversation_sessions"
    )
    op.drop_column("conversation_sessions", "owner_id")
