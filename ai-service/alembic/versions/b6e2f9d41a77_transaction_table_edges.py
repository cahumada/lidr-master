"""transaction_table_edges y transaction_table_builds

Revision ID: b6e2f9d41a77
Revises: a4c19d7e2b58
Create Date: 2026-09-11 10:00:00.000000

The tables a transaction touches, materialized per MIRROR run from Oracle's
dependency graph. Keyed by `run_id` and not by `doc_version`: what the row
asserts is what Oracle declared in that extraction run.

`transaction_table_builds` answers "does this run have edges?" without a COUNT,
and -- the reason it exists -- keeps zero edges distinguishable from a build
that never ran.

|| Las tablas que toca una transacción, materializadas por corrida del MIRROR
desde el grafo de dependencias de Oracle. `transaction_table_builds` responde
«¿esta corrida tiene aristas?» y mantiene distinguible cero aristas de un batch
que nunca corrió.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b6e2f9d41a77"
down_revision: str | None = "a4c19d7e2b58"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "transaction_table_edges",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant", sa.String(length=100), nullable=False),
        sa.Column("env", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_code", sa.String(length=64), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("role_reason", sa.Text(), nullable=False),
        sa.Column("via_routines", sa.Text(), nullable=False),
        sa.Column("fan_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("routine_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("routine_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant",
            "env",
            "run_id",
            "transaction_code",
            "table_name",
            name="uq_transaction_table_edges_identity",
        ),
    )
    op.create_index(
        "ix_transaction_table_edges_code",
        "transaction_table_edges",
        ["tenant", "env", "run_id", "transaction_code"],
    )

    op.create_table(
        "transaction_table_builds",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant", sa.String(length=100), nullable=False),
        sa.Column("env", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("code_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("doc_version", sa.String(length=128), nullable=False),
        sa.Column(
            "built_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant", "env", "run_id", name="uq_transaction_table_builds_identity"
        ),
    )


def downgrade() -> None:
    op.drop_table("transaction_table_builds")
    op.drop_index(
        "ix_transaction_table_edges_code", table_name="transaction_table_edges"
    )
    op.drop_table("transaction_table_edges")
