"""Postgres checkpointer wiring for the answer-orchestration graph.

Uses the same ``DATABASE_URL`` as pgvector; the checkpointer creates its own
tables and coexists with ``chunks``. LangGraph's ``AsyncPostgresSaver`` wants a
plain libpq DSN, not SQLAlchemy's ``+psycopg`` / ``+asyncpg`` forms.

|| Cableado del checkpointer Postgres para el grafo de orquestación. Usa el
mismo ``DATABASE_URL`` que pgvector; el checkpointer crea sus propias tablas y
coexiste con ``chunks``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import Settings, get_settings
from app.foundation.persistence.database import to_sync_url

log = structlog.get_logger()

_CONNECTION_KWARGS = {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 10


def saver_conninfo(settings: Settings | None = None) -> str:
    """Return a plain libpq DSN for ``AsyncPostgresSaver``.

    || Devuelve un DSN libpq plano para ``AsyncPostgresSaver``.
    """
    url = to_sync_url((settings or get_settings()).DATABASE_URL)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Open a pooled ``AsyncPostgresSaver`` and set up its tables.

    || Abre un ``AsyncPostgresSaver`` con pool y crea sus tablas.
    """
    conninfo = saver_conninfo()
    if "connect_timeout" not in conninfo:
        separator = "&" if "?" in conninfo else "?"
        conninfo = f"{conninfo}{separator}connect_timeout=3"
    pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=_POOL_MIN_SIZE,
        max_size=_POOL_MAX_SIZE,
        kwargs=_CONNECTION_KWARGS,
        open=False,
    )
    await pool.open(wait=True)
    try:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        log.info("answer_graph_checkpointer_ready", pool_max=_POOL_MAX_SIZE)
        yield checkpointer
    finally:
        await pool.close()
