"""SessionStore against a real Postgres, or a skip that says why not.

JSONB round-trips and a TTL comparison against a ``timestamptz`` are database
behavior. An in-memory double would be testing the double, so these tests say
what they need and skip -- with the reason -- when it is not there. Same rule
as ``tests/store/conftest.py``: a test that skips silently is worse than no
test.

The async plumbing is hand-rolled on ``asyncio.run`` rather than pulled in
with ``pytest-asyncio``, because that is what every other async test in this
repo does and one integration file is not a reason to add a dependency.

|| SessionStore contra un Postgres real, o un skip que dice por qué no. El
round-trip de JSONB y una comparación de TTL contra un ``timestamptz`` son
comportamiento de la base; un doble en memoria testearía el doble. La
plomería async va a mano sobre ``asyncio.run`` y no con ``pytest-asyncio``
porque es lo que hace cada otro test async del repo, y un archivo de
integración no justifica una dependencia nueva.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.foundation.persistence.database import Base, to_async_url, to_sync_url
from app.generation.conversation.models import (
    Anchor,
    ConversationFacts,
    HistoryTurn,
    Turn,
)
from app.generation.conversation.store import ConversationSessionRow, SessionStore

TEST_SCHEMA = "conversation_tests"
TTL_DAYS = 30


def _unreachable_reason(url: str) -> str | None:
    """Why the database cannot be used, or ``None`` if it can.

    || Por qué no se puede usar la base, o ``None`` si sí se puede.
    """
    try:
        # 10s and not 3: `DATABASE_URL` can point at a managed Postgres over
        # the internet, where a 3-second budget covers the TLS handshake and
        # little else -- and the skip that follows would then blame "no
        # database" for what is really a slow one.
        # || 10s y no 3: `DATABASE_URL` puede apuntar a un Postgres gestionado
        # a través de internet, donde 3 segundos apenas cubren el handshake
        # TLS, y el skip culparía a "no hay base" por una base lenta.
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return f"no reachable Postgres at {url.rsplit('@', 1)[-1]} ({type(error).__name__})"
    return None


@pytest.fixture(scope="session")
def test_schema() -> Iterator[str]:
    """Create the throwaway schema and its one table, ONCE for the module.

    Session-scoped for a reason measured rather than assumed: against a
    managed Postgres over the internet a single connect costs ~10-25s, so a
    per-test schema would spend minutes doing setup and seconds testing. Same
    shape as ``tests/store/conftest.py``, whose engine is session-scoped too.

    || Crea el esquema descartable y su única tabla UNA vez por módulo. De
    alcance sesión por una razón medida y no supuesta: contra un Postgres
    gestionado por internet una conexión cuesta ~10-25s, así que un esquema
    por test gastaría minutos en preparar y segundos en probar.
    """
    settings = get_settings()
    sync_url = to_sync_url(settings.DATABASE_URL)
    reason = _unreachable_reason(sync_url)
    if reason is not None:
        pytest.skip(f"integration test needs a database: {reason}. Try `docker compose up -d`.")

    setup_engine = create_engine(sync_url, connect_args={"connect_timeout": 30})
    with setup_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        connection.commit()
    with setup_engine.connect() as connection:
        # checkfirst=False for the same reason as the store tests: with a
        # search_path set, the existence check can resolve to a table in
        # `public` and skip creating the test one.
        # || checkfirst=False por lo mismo que en los tests del store: con
        # search_path puesto, el chequeo de existencia puede resolver a una
        # tabla de `public` y saltear la de test.
        connection.execute(text(f"SET search_path TO {TEST_SCHEMA},public"))
        Base.metadata.create_all(
            connection, tables=[ConversationSessionRow.__table__], checkfirst=False
        )
        connection.commit()

    yield TEST_SCHEMA

    with setup_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.commit()
    setup_engine.dispose()


@pytest.fixture
def run_with_store(test_schema: str) -> Callable[[Callable[[SessionStore], Awaitable[Any]]], Any]:
    """Run one coroutine against an empty ``conversation_sessions``.

    The table is emptied before each scenario instead of rebuilt, so order
    never matters and the cost per test is one DELETE.

    || Corre una corutina contra un ``conversation_sessions`` vacío. La tabla
    se vacía antes de cada escenario en vez de reconstruirse, así el orden
    nunca importa y el costo por test es un DELETE.
    """
    settings = get_settings()

    def _run(scenario: Callable[[SessionStore], Awaitable[Any]]) -> Any:
        async def _main() -> Any:
            # `to_async_url`, not the raw setting: `DATABASE_URL` may carry no
            # driver token at all, and `create_async_engine` on a bare
            # `postgresql://` picks a SYNC dialect and dies importing psycopg2.
            # || `to_async_url` y no el setting crudo: `DATABASE_URL` puede no
            # traer token de driver, y `create_async_engine` sobre un
            # `postgresql://` pelado elige un dialecto SÍNCRONO y muere
            # importando psycopg2.
            engine = create_async_engine(
                to_async_url(settings.DATABASE_URL),
                connect_args={"server_settings": {"search_path": f"{test_schema},public"}},
            )
            try:
                factory = async_sessionmaker(engine, expire_on_commit=False)
                async with factory() as session:
                    await session.execute(delete(ConversationSessionRow))
                    await session.commit()
                    return await scenario(SessionStore(session, ttl_days=TTL_DAYS))
            finally:
                await engine.dispose()

        return asyncio.run(_main())

    return _run


async def _age(store: SessionStore, session_id: str, days: int) -> None:
    """Backdate a row so the TTL can be exercised. || Envejece una fila."""
    row = await store._session.get(ConversationSessionRow, session_id)
    row.updated_at = datetime.now(UTC) - timedelta(days=days)
    await store._session.commit()


def test_a_created_session_can_be_read_back(run_with_store):
    async def scenario(store: SessionStore):
        created = await store.create()
        found = await store.get(created.session_id)
        assert found is not None
        assert found.session_id == created.session_id
        assert found.facts.is_empty()

    run_with_store(scenario)


def test_facts_anchors_and_turns_survive_the_round_trip(run_with_store):
    async def scenario(store: SessionStore):
        conversation = await store.create()
        conversation.facts = ConversationFacts(
            module_code=["CA"], last_document_ids=["CA014"]
        )
        conversation.pin(
            [Anchor(kind="module_code", value="CA", source_question="solo módulo CA")]
        )
        conversation.append_turn(
            Turn(
                question="¿y eso?",
                resolved_question="¿y eso? (sobre CA014)",
                answer="texto",
            ),
            max_turns=4,
        )
        await store.save(conversation)

        found = await store.get(conversation.session_id)
        assert found is not None
        assert found.facts.last_document_ids == ["CA014"]
        assert [(a.kind, a.value) for a in found.anchors] == [("module_code", "CA")]
        assert found.turns[0].resolved_question == "¿y eso? (sobre CA014)"

    run_with_store(scenario)


def test_an_unknown_session_is_none(run_with_store):
    async def scenario(store: SessionStore):
        assert await store.get("no-existe") is None

    run_with_store(scenario)


def test_an_expired_session_reads_as_absent(run_with_store):
    """Indistinguishable from missing on purpose: the turn answers without memory.

    || Indistinguible de inexistente a propósito: el turno responde sin memoria.
    """

    async def scenario(store: SessionStore):
        conversation = await store.create()
        await _age(store, conversation.session_id, TTL_DAYS + 1)
        assert await store.get(conversation.session_id) is None

    run_with_store(scenario)


def test_deleting_is_idempotent(run_with_store):
    """"Start a new thread" must not fail because the old one had expired.

    || «Empezar un hilo nuevo» no puede fallar porque el anterior venció.
    """

    async def scenario(store: SessionStore):
        conversation = await store.create()
        assert await store.delete(conversation.session_id) is True
        assert await store.delete(conversation.session_id) is False
        assert await store.get(conversation.session_id) is None

    run_with_store(scenario)


def test_purge_removes_only_what_expired(run_with_store):
    async def scenario(store: SessionStore):
        fresh = await store.create()
        stale = await store.create()
        await _age(store, stale.session_id, TTL_DAYS + 10)

        assert await store.purge_expired() == 1
        assert await store.get(fresh.session_id) is not None

    run_with_store(scenario)


def test_list_recent_skips_empty_and_expired_and_orders_newest_first(run_with_store):
    async def scenario(store: SessionStore):
        empty = await store.create()
        older = await store.create()
        older.append_history(
            HistoryTurn(question="primera", resolved_question="primera", answer="a")
        )
        await store.save(older)
        newer = await store.create()
        newer.append_history(
            HistoryTurn(question="segunda", resolved_question="segunda", answer="b")
        )
        await store.save(newer)
        expired = await store.create()
        expired.append_history(
            HistoryTurn(question="vieja", resolved_question="vieja", answer="c")
        )
        await store.save(expired)
        await _age(store, expired.session_id, TTL_DAYS + 1)

        listed = await store.list_recent(limit=50, offset=0)
        ids = [item.session_id for item in listed]

        assert empty.session_id not in ids
        assert expired.session_id not in ids
        assert ids == [newer.session_id, older.session_id]

        page = await store.list_recent(limit=1, offset=0)
        assert [item.session_id for item in page] == [newer.session_id]

    run_with_store(scenario)


def test_rename_updates_the_title(run_with_store):
    async def scenario(store: SessionStore):
        conversation = await store.create()
        conversation.append_history(
            HistoryTurn(question="original", resolved_question="original", answer="a")
        )
        await store.save(conversation)

        renamed = await store.rename(conversation.session_id, "nuevo nombre")
        assert renamed is not None
        assert renamed.title == "nuevo nombre"
        assert (await store.get(conversation.session_id)).title == "nuevo nombre"

    run_with_store(scenario)


def test_rename_of_an_expired_session_is_absent(run_with_store):
    async def scenario(store: SessionStore):
        conversation = await store.create()
        await _age(store, conversation.session_id, TTL_DAYS + 1)
        assert await store.rename(conversation.session_id, "no") is None

    run_with_store(scenario)


def test_a_backfilled_row_exposes_history_on_get(run_with_store):
    """The migration copies `turns` → `history`. get must read that copy.

    || La migración copia `turns` → `history`. get tiene que leer esa copia.
    """

    async def scenario(store: SessionStore):
        conversation = await store.create()
        conversation.append_turn(
            Turn(question="¿CA014?", resolved_question="¿CA014?", answer="preview"),
            max_turns=4,
        )
        await store.save(conversation)

        row = await store._session.get(ConversationSessionRow, conversation.session_id)
        assert row is not None
        row.history = list(row.turns)
        row.title = (row.turns[0].get("question") or "")[:80]
        await store._session.commit()
        store._session.expire_all()

        found = await store.get(conversation.session_id)
        assert found is not None
        assert found.title == "¿CA014?"
        assert len(found.history) == 1
        assert found.history[0].question == "¿CA014?"
        assert found.history[0].citations == []

    run_with_store(scenario)
