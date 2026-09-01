"""Engine, session factories and the declarative ``Base``.

Mirrors ``app/foundation/persistence/database.py`` on the ``session_16`` branch
of LIDR-academy/ai-engineering, including its two-stack split: a synchronous
engine (psycopg) for the offline bulk load, where ``COPY`` is the simplest and
fastest thing there is, and an asynchronous one (asyncpg) for the query path,
which will sit inside an HTTP request and must not block the event loop.

Both come from one ``DATABASE_URL``; the async side swaps the driver token, so
there is no second setting to keep in sync.

|| Engine, factories de sesión y la ``Base`` declarativa.

Replica ``app/foundation/persistence/database.py`` de la rama ``session_16`` de
LIDR-academy/ai-engineering, incluida su división en dos stacks: un engine
sincrónico (psycopg) para la carga masiva offline, donde ``COPY`` es lo más
simple y lo más rápido, y uno asincrónico (asyncpg) para el camino de consulta,
que va a estar dentro de un request HTTP y no debe bloquear el event loop.

Los dos salen de un solo ``DATABASE_URL``; el lado async le cambia el token del
driver, así que no hay un segundo setting que mantener sincronizado.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base. Alembic's ``env.py`` reads its metadata to autogenerate.

    || Base declarativa. El ``env.py`` de Alembic lee su metadata para autogenerar.
    """


def to_async_url(url: str) -> str:
    """Rewrite a psycopg URL as its asyncpg equivalent.

    One setting, two stacks: a second URL would be one more thing that can
    silently point somewhere else.

    || Reescribe una URL de psycopg como su equivalente de asyncpg. Un solo
    setting, dos stacks: una segunda URL sería una cosa más que puede terminar
    apuntando a otro lado sin que nadie lo note.
    """
    if "+asyncpg" in url:
        return url
    if "+psycopg" in url:
        return url.replace("+psycopg", "+asyncpg", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def to_sync_url(url: str) -> str:
    """Rewrite an asyncpg URL as its psycopg equivalent.

    || Reescribe una URL de asyncpg como su equivalente de psycopg.
    """
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _apply_pgvector_session_settings(dbapi_connection, _record) -> None:
    """Set pgvector's scan behaviour on every new connection.

    A property of how this application queries, so it belongs on the connection
    and not repeated in each query -- one query that forgets it comes back with
    silently wrong results.

    || Fija el comportamiento de escaneo de pgvector en cada conexión nueva. Es
    una propiedad de cómo consulta esta aplicación, así que va en la conexión y
    no repetida en cada consulta — una consulta que se olvide vuelve con
    resultados equivocados en silencio.
    """
    settings = get_settings()
    # Opened and closed by hand rather than with `with`: psycopg3's cursor is a
    # context manager and SQLAlchemy's asyncpg adapter's is not.
    # || Se abre y se cierra a mano en vez de con `with`: el cursor de psycopg3
    # es un context manager y el del adaptador asyncpg de SQLAlchemy no.
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"SET hnsw.iterative_scan = {settings.HNSW_ITERATIVE_SCAN}")
        cursor.execute(f"SET hnsw.max_scan_tuples = {settings.HNSW_MAX_SCAN_TUPLES}")
    finally:
        cursor.close()


@lru_cache
def get_engine() -> Engine:
    """Synchronous engine, for migrations and the bulk load.

    || Engine sincrónico, para las migraciones y la carga masiva.
    """
    engine = create_engine(to_sync_url(get_settings().DATABASE_URL), pool_pre_ping=True)
    event.listen(engine, "connect", _apply_pgvector_session_settings)
    return engine


@lru_cache
def get_async_engine() -> AsyncEngine:
    """Asynchronous engine, for the query path.

    || Engine asincrónico, para el camino de consulta.
    """
    engine = create_async_engine(to_async_url(get_settings().DATABASE_URL), pool_pre_ping=True)
    # The listener goes on `sync_engine`: SQLAlchemy's asyncpg dialect wraps the
    # connection in an adapter that emulates a DBAPI cursor, so the same
    # connect-time SET works on both stacks.
    # || El listener va en `sync_engine`: el dialecto asyncpg de SQLAlchemy
    # envuelve la conexión en un adaptador que emula un cursor DBAPI, así que el
    # mismo SET al conectar sirve para los dos stacks.
    event.listen(engine.sync_engine, "connect", _apply_pgvector_session_settings)
    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@lru_cache
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_async_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a synchronous session and close it on exit.

    || Entrega una sesión sincrónica y la cierra al salir.
    """
    with get_session_factory()() as session:
        yield session


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield an asynchronous session and close it on exit.

    || Entrega una sesión asincrónica y la cierra al salir.
    """
    async with get_async_session_factory()() as session:
        yield session
