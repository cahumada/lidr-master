"""conversation_sessions: title + durable history

Revision ID: c4e8a91b07d2
Revises: f3a7c21e9b40
Create Date: 2026-09-06 21:50:00.000000

Cuarto slot: el transcript que la consola relee. `turns` sigue siendo la
ventana de memoria (4 pares, respuesta recortada). `history` no se recorta.
El backfill copia lo único recuperable — los `turns` actuales — y toma el
título de la primera pregunta. Las filas viejas quedan con como mucho 4
previews y sin citas; no se inventa procedencia.

|| Fourth slot: the transcript the console rereads. `turns` stays the memory
window. Backfill copies what is recoverable — current `turns` — and titles
from the first question. Old rows keep at most 4 previews and no citations.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4e8a91b07d2"
down_revision: str | None = "f3a7c21e9b40"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_sessions",
        sa.Column("title", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "conversation_sessions",
        sa.Column(
            "history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE conversation_sessions
            SET history = turns
            WHERE history = '[]'::jsonb
              AND turns != '[]'::jsonb
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE conversation_sessions
            SET title = left(
                btrim(regexp_replace(turns -> 0 ->> 'question', '\\s+', ' ', 'g')),
                80
            )
            WHERE title IS NULL
              AND jsonb_array_length(turns) > 0
            """
        )
    )


def downgrade() -> None:
    op.drop_column("conversation_sessions", "history")
    op.drop_column("conversation_sessions", "title")
