"""window_status en chunks

Revision ID: f1a8b3c92d04
Revises: e7b2c4a91f03
Create Date: 2026-09-09 21:30:00.000000

Declared record status from WINDOWS.SSTATREGT / TABLE26. Metadata only — no
index because this change does not filter on it.

|| Estado declarado del registro desde WINDOWS.SSTATREGT / TABLE26. Solo
metadata — sin índice porque este change no filtra por él.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f1a8b3c92d04"
down_revision: str | None = "e7b2c4a91f03"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("window_status", sa.String(length=48), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "window_status")
