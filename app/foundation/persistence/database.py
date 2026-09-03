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
from sqlalchemy.engine import make_url
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


# libpq spells the TLS mode `sslmode`; asyncpg's `connect()` spells it `ssl`.
# The VALUES are the same vocabulary -- disable / allow / prefer / require /
# verify-ca / verify-full, parsed by asyncpg's own `SSLMode.parse` -- so this is
# a rename and never a translation of meaning.
#
# Why it matters: asyncpg DOES understand `sslmode`, but only inside a DSN it
# parses itself. SQLAlchemy's asyncpg dialect does not pass a DSN -- it passes
# individual kwargs to `asyncpg.connect()`, whose signature has no `sslmode` and
# no `**kwargs`. So a managed Postgres URL with `?sslmode=require` fails at
# connect time on the async path ONLY: psycopg accepts it, so migrations and the
# bulk COPY succeed and `GET /search` is the one thing that breaks. That is the
# worst shape a failure can have -- everything looks like it worked.
# || libpq lo llama `sslmode`; el `connect()` de asyncpg lo llama `ssl`. Los
# VALORES son el mismo vocabulario, parseados por el propio `SSLMode.parse` de
# asyncpg, así que esto es un renombre y nunca una traducción de significado.
#
# Por qué importa: asyncpg SÍ entiende `sslmode`, pero solo dentro de un DSN que
# parsea él. El dialecto asyncpg de SQLAlchemy no le pasa un DSN — le pasa
# kwargs a `asyncpg.connect()`, que no tiene `sslmode` ni `**kwargs`. Así que una
# URL de Postgres gestionado con `?sslmode=require` falla al conectar SOLO en el
# camino async: psycopg la acepta, así que las migraciones y el COPY masivo
# andan y `GET /search` es lo único que se rompe. Es la peor forma que puede
# tener una falla: todo parece haber funcionado.
_LIBPQ_TLS_MODE = "sslmode"
_ASYNCPG_TLS_MODE = "ssl"


def to_async_url(url: str) -> str:
    """Rewrite a psycopg URL as its asyncpg equivalent.

    One setting, two stacks: a second URL would be one more thing that can
    silently point somewhere else.

    || Reescribe una URL de psycopg como su equivalente de asyncpg. Un solo
    setting, dos stacks: una segunda URL sería una cosa más que puede terminar
    apuntando a otro lado sin que nadie lo note.
    """
    parsed = make_url(url)
    if parsed.drivername.startswith("postgresql"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    if _LIBPQ_TLS_MODE in parsed.query:
        query = dict(parsed.query)
        query[_ASYNCPG_TLS_MODE] = query.pop(_LIBPQ_TLS_MODE)
        parsed = parsed.set(query=query)
    return parsed.render_as_string(hide_password=False)


def to_sync_url(url: str) -> str:
    """Rewrite an asyncpg URL as its psycopg equivalent.

    || Reescribe una URL de asyncpg como su equivalente de psycopg.
    """
    parsed = make_url(url)
    if parsed.drivername.startswith("postgresql"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    if _ASYNCPG_TLS_MODE in parsed.query:
        query = dict(parsed.query)
        query[_LIBPQ_TLS_MODE] = query.pop(_ASYNCPG_TLS_MODE)
        parsed = parsed.set(query=query)
    return parsed.render_as_string(hide_password=False)


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
