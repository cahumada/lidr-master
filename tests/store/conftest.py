"""Fixtures for the store tests.

pgvector cannot be emulated: cosine distance, HNSW and the Spanish dictionary
of ``to_tsvector`` are Postgres, and an in-memory double would be testing
something else. So the tests that need a database say so, and skip -- with the
reason -- when there is none. A test that skips silently is worse than no test.

|| Fixtures de los tests del store. pgvector no se puede emular: la distancia
coseno, HNSW y el diccionario español de ``to_tsvector`` son Postgres, y un
doble en memoria testearía otra cosa. Así que los tests que necesitan base lo
dicen, y se saltean —con el motivo— cuando no hay ninguna. Un test que se
saltea en silencio es peor que no tenerlo.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings
from app.foundation.persistence.database import (
    _apply_pgvector_session_settings,
    to_sync_url,
)

# The schema every store integration test writes into. A separate one so a test
# run can never touch the real corpus, and so the whole thing can be dropped at
# the end no matter how a test failed.
# || El esquema en el que escriben los tests de integración del store. Aparte,
# para que una corrida no pueda tocar el corpus real y para poder tirarlo entero
# al final sin importar cómo falló un test.
TEST_SCHEMA = "store_tests"


def _unreachable_reason(url: str) -> str | None:
    """Why the database cannot be used, or ``None`` if it can.

    || Por qué no se puede usar la base, o ``None`` si sí se puede.
    """
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with engine.connect() as connection:
            available = connection.execute(
                text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
            ).first()
            if available is None:
                return "the server has no pgvector extension available"
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return f"no reachable Postgres at {url.rsplit('@', 1)[-1]} ({type(error).__name__})"
    return None


@pytest.fixture(scope="session")
def database_url() -> str:
    return to_sync_url(get_settings().DATABASE_URL)


@pytest.fixture(scope="session")
def store_engine(database_url: str) -> Iterator[Engine]:
    """An engine pointed at a throwaway schema, or a skip explaining why not.

    || Un engine apuntado a un esquema descartable, o un skip que explica por qué no.
    """
    reason = _unreachable_reason(database_url)
    if reason is not None:
        pytest.skip(f"integration test needs a database: {reason}. Try `docker compose up -d`.")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        # Everything this engine does lands in the test schema, including the
        # tables SQLAlchemy creates from the models.
        # || Todo lo que hace este engine cae en el esquema de test, incluidas
        # las tablas que SQLAlchemy crea a partir de los modelos.
        connect_args={"options": f"-csearch_path={TEST_SCHEMA},public"},
    )
    from sqlalchemy import event

    event.listen(engine, "connect", _apply_pgvector_session_settings)

    with create_engine(database_url).connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        connection.commit()

    from app.foundation.persistence.database import Base
    from app.generation.rag.store import models  # noqa: F401 -- registers the tables

    # checkfirst=False on purpose: with `search_path` set, SQLAlchemy's
    # existence check resolves `chunks` to the one in `public` -- the real
    # corpus -- and skips creating the test one. The tables would then be
    # missing and every test would write into production.
    # || checkfirst=False a propósito: con el `search_path` puesto, el chequeo
    # de existencia de SQLAlchemy resuelve `chunks` al de `public` —el corpus
    # real— y saltea crear el de test. Las tablas quedarían sin crear y cada
    # test escribiría en producción.
    Base.metadata.create_all(engine, checkfirst=False)
    yield engine

    engine.dispose()
    with create_engine(database_url).connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.commit()


@pytest.fixture
def clean_tables(store_engine: Engine) -> Iterator[Engine]:
    """Empty both tables before each test, so order never matters.

    || Vacía las dos tablas antes de cada test, así el orden nunca importa.
    """
    with store_engine.connect() as connection:
        connection.execute(text(f"TRUNCATE {TEST_SCHEMA}.chunks, {TEST_SCHEMA}.corpus_versions"))
        connection.commit()
    return store_engine


@pytest.fixture
def tenant() -> str:
    """A tenant id unique to this test. || Un id de cliente único de este test."""
    return f"t_{uuid.uuid4().hex[:8]}"
