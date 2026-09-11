"""business_db_selection y business_db_stamp

Revision ID: a4c19d7e2b58
Revises: f1a8b3c92d04
Create Date: 2026-09-10 20:10:00.000000

Which mirror run the service reads from, and which run stamped the corpus.

Both tables live in OUR schema and nothing here touches `visualtime.*`: that
schema is written by `dw-oracle-extractor`, and an `is_active` column added
there would turn the mirror into shared space with two owners.

The partial unique index is the point of the first table. At most one active run
per client is guaranteed by the DATABASE and not by application code, which is
the same reasoning `corpus_versions` already wrote down for its single active
version: the rule held only in code breaks under two concurrent processes.

|| Con qué corrida del mirror lee el servicio, y con cuál se estampó el corpus.
Las dos tablas viven en NUESTRO esquema y acá no se toca `visualtime.*`: ese
esquema lo escribe otro repo, y un `is_active` ahí volvería el mirror un espacio
compartido con dos dueños. El índice parcial único es el punto de la primera
tabla: a lo sumo una corrida activa por cliente, garantizado por la BASE.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a4c19d7e2b58"
down_revision: str | None = "f1a8b3c92d04"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "business_db_selection",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("env", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Declared by the caller, never verified: the service authenticates the
        # caller with a shared token, and a token is not a person.
        # || Declarado por quien llama, nunca verificado: el token autentica al
        # llamador, y un token no es una persona.
        sa.Column("activated_by", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "env", "run_id", name="uq_business_db_selection_tenant_env_run"
        ),
    )
    # NOT keyed by `env`: the service reads from one run, period. One active per
    # environment would mean two answers depending on which env was asked about.
    # || NO va por `env`: el servicio lee de una corrida y punto.
    op.create_index(
        "uq_business_db_selection_one_active_per_tenant",
        "business_db_selection",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "business_db_stamp",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("doc_version", sa.String(length=128), nullable=False),
        sa.Column("env", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column(
            "stamped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Zero is a real answer -- the corpus had nothing to stamp -- so it is
        # recorded instead of treated as a failure.
        # || Cero es una respuesta real y se registra, no se trata como falla.
        sa.Column("rows_updated", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "doc_version", name="uq_business_db_stamp_tenant_doc_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("business_db_stamp")
    op.drop_index(
        "uq_business_db_selection_one_active_per_tenant", table_name="business_db_selection"
    )
    op.drop_table("business_db_selection")
