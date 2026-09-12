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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.foundation.persistence.database import Base, to_async_url, to_sync_url
from app.generation.conversation.models import (
    Anchor,
    ConversationFacts,
    ConversationSession,
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

    The store handed over is the OWNERLESS one, which is a real caller and not
    a placeholder: evals and scripts talk to the service with no identity and
    see exactly the conversations they create. Ownership across owners is
    exercised by ``run_with_owned_stores``.

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
                    return await scenario(
                        SessionStore(session, ttl_days=TTL_DAYS, owner_id=None)
                    )
            finally:
                await engine.dispose()

        return asyncio.run(_main())

    return _run


@pytest.fixture
def run_with_owned_stores(test_schema: str):
    """Run one coroutine with a factory that builds a store per owner.

    All the stores share one database session, which is what makes the
    assertions about isolation mean something: the separation being tested is
    the ``WHERE``, not two connections that could not see each other anyway.

    || Corre una corutina con una factory que arma un store por dueño. Todos
    comparten una sola sesión de base, que es lo que hace que las aserciones
    de aislamiento signifiquen algo: lo que se prueba es el ``WHERE``, no dos
    conexiones que de todos modos no se verían.
    """
    settings = get_settings()

    def _run(scenario):
        async def _main():
            engine = create_async_engine(
                to_async_url(settings.DATABASE_URL),
                connect_args={"server_settings": {"search_path": f"{test_schema},public"}},
            )
            try:
                factory = async_sessionmaker(engine, expire_on_commit=False)
                async with factory() as session:
                    await session.execute(delete(ConversationSessionRow))
                    await session.commit()

                    def store_for(owner_id: str | None) -> SessionStore:
                        return SessionStore(
                            session, ttl_days=TTL_DAYS, owner_id=owner_id
                        )

                    return await scenario(store_for)
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


# --------------------------------------------------------------------------
# Ownership || Pertenencia
#
# The leak these fix: before `owner_id`, every person logged into the console
# listed, reopened, renamed and deleted everybody else's conversations.
# || La fuga que arreglan: antes de `owner_id`, cualquiera logueado en la
# consola listaba, reabría, renombraba y borraba las de todos.
# --------------------------------------------------------------------------


async def _closed_conversation(store: SessionStore) -> str:
    """A conversation with one closed turn, so it shows up in listings.

    || Una conversación con un turno cerrado, para que aparezca en listados.
    """
    conversation = await store.create()
    conversation.append_history(
        HistoryTurn(
            question="¿qué hace CA014?",
            resolved_question="¿qué hace CA014?",
            answer="lo que sea",
        )
    )
    await store.save(conversation)
    return conversation.session_id


def test_the_listing_of_one_owner_never_carries_another_owners_conversation(
    run_with_owned_stores,
):
    """The regression test for the leak itself, named after what it prevents.

    || El test de regresión de la fuga, nombrado por lo que previene.
    """

    async def scenario(store_for):
        ada, bruno = store_for("user_ada"), store_for("user_bruno")
        ada_session = await _closed_conversation(ada)
        bruno_session = await _closed_conversation(bruno)

        ada_listed = await ada.list_recent(limit=50, offset=0)
        bruno_listed = await bruno.list_recent(limit=50, offset=0)

        assert [item.session_id for item in ada_listed] == [ada_session]
        assert [item.session_id for item in bruno_listed] == [bruno_session]

    run_with_owned_stores(scenario)


def test_another_owners_conversation_reads_as_absent(run_with_owned_stores):
    async def scenario(store_for):
        ada, bruno = store_for("user_ada"), store_for("user_bruno")
        bruno_session = await _closed_conversation(bruno)

        assert await ada.get(bruno_session) is None

    run_with_owned_stores(scenario)


def test_another_owners_conversation_cannot_be_renamed_or_deleted(run_with_owned_stores):
    async def scenario(store_for):
        ada, bruno = store_for("user_ada"), store_for("user_bruno")
        bruno_session = await _closed_conversation(bruno)

        assert await ada.rename(bruno_session, "mío ahora") is None
        assert await ada.delete(bruno_session) is False

        # Still there, still Bruno's, still named what he named it.
        # || Sigue ahí, sigue siendo de Bruno, y con su nombre.
        survivor = await bruno.get(bruno_session)
        assert survivor is not None
        assert survivor.title != "mío ahora"

    run_with_owned_stores(scenario)


def test_no_identity_is_a_bucket_and_not_a_wildcard(run_with_owned_stores):
    """The requirement that breaks most easily on a refactor.

    Absence of identity must see the ownerless conversations and NOTHING else.
    If it ever meant "no filter", the whole protection would be turned off by
    dropping a header.

    || El requisito que más fácil se rompe al refactorizar: la ausencia de
    identidad ve las conversaciones sin dueño y NADA más.
    """

    async def scenario(store_for):
        nobody, ada = store_for(None), store_for("user_ada")
        orphan = await _closed_conversation(nobody)
        ada_session = await _closed_conversation(ada)

        listed = [item.session_id for item in await nobody.list_recent(limit=50, offset=0)]
        assert listed == [orphan]
        assert await nobody.get(ada_session) is None

        # And the owner does not inherit the ownerless ones either.
        # || Y el dueño tampoco hereda las que no tienen dueño.
        assert await ada.get(orphan) is None

    run_with_owned_stores(scenario)


def test_saving_cannot_take_over_an_existing_conversation(run_with_owned_stores):
    """A save under somebody else's id must not change the row's owner.

    || Guardar con el id de otro no puede cambiarle el dueño a la fila.
    """

    async def scenario(store_for):
        ada, bruno = store_for("user_ada"), store_for("user_bruno")
        bruno_session = await _closed_conversation(bruno)

        stolen = ConversationSession(session_id=bruno_session, owner_id="user_ada")
        stolen.append_history(
            HistoryTurn(question="mía", resolved_question="mía", answer="mía")
        )
        # The row already exists under another owner, so the INSERT this save
        # falls back to collides on the primary key instead of taking it over.
        # || La fila ya existe con otro dueño, así que el INSERT al que cae
        # este save choca contra la PK en vez de quedársela.
        with pytest.raises(IntegrityError):
            await ada.save(stolen)

    run_with_owned_stores(scenario)


def test_the_ttl_sweep_reaches_every_owner(run_with_owned_stores):
    """Expiring is the clock's business, not the caller's.

    || Vencer es del reloj, no de quien pregunta.
    """

    async def scenario(store_for):
        ada, bruno = store_for("user_ada"), store_for("user_bruno")
        ada_session = await _closed_conversation(ada)
        bruno_session = await _closed_conversation(bruno)
        await _age(ada, ada_session, TTL_DAYS + 1)
        await _age(bruno, bruno_session, TTL_DAYS + 1)

        assert await ada.purge_expired() == 2

    run_with_owned_stores(scenario)
