"""Alembic environment.

The URL comes from ``Settings.DATABASE_URL``, never from ``alembic.ini``: a
connection string in a versioned file is a credential waiting to be committed,
and it would also let the migrations point somewhere other than the app.

|| Entorno de Alembic. La URL sale de ``Settings.DATABASE_URL``, nunca de
``alembic.ini``: una cadena de conexión en un archivo versionado es una
credencial esperando ser commiteada, y además dejaría que las migraciones
apunten a otro lado que la aplicación.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.foundation.persistence.database import Base, to_sync_url

# Imported for the side effect of registering the tables on Base.metadata, which
# is what autogenerate compares against.
# || Se importa por el efecto de registrar las tablas en Base.metadata, que es
# contra lo que compara autogenerate.
from app.domain import profiles  # noqa: F401
from app.generation.rag.store import models  # noqa: F401
from app.ingestion import jobs  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", to_sync_url(get_settings().DATABASE_URL))

target_metadata = Base.metadata

# Tablas que otra herramienta crea y administra: el `AsyncPostgresSaver` de
# LangGraph las arma en el arranque del servicio y no las declara en
# `Base.metadata`. Sin este filtro, autogenerate las ve "de mas" y propone
# borrarlas -- lo que borraria cada hilo pausado esperando revision humana.
# Verificado: la primera autogeneracion despues de agregar el checkpointer
# incluia esos cuatro `drop_table`.
# || Tables another tool owns: LangGraph's `AsyncPostgresSaver` creates them at
# service startup and never declares them on `Base.metadata`. Without this
# filter, autogenerate sees them as extra and proposes dropping them -- which
# would delete every thread paused for human review. Verified: the first
# autogenerate after adding the checkpointer included those four drops.
_FOREIGN_TABLES = frozenset(
    {
        "checkpoints",
        "checkpoint_writes",
        "checkpoint_blobs",
        "checkpoint_migrations",
    }
)


def include_name(name, type_, parent_names):
    """Keep foreign-owned tables out of the autogenerate comparison.

    || Deja las tablas de otra herramienta fuera de la comparacion.
    """
    if type_ == "table":
        return name not in _FOREIGN_TABLES
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
