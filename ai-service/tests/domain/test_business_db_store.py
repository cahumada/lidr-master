"""Which mirror run wins, and what the database refuses.

The precedence rule IS the change: the selection beats the configured default,
the default is never written as a row, and "the latest run" is never an answer.
These tests pin each of those, plus the one invariant that is NOT held in
Python — at most one active run per tenant, enforced by a partial unique index.

Against a real Postgres, in a throwaway schema, with the async plumbing hand
rolled on ``asyncio.run``. Same shape and same reasons as
``tests/generation/conversation/test_store.py``: a partial index is database
behaviour and an in-memory double would be testing the double, and one
integration file is not a reason to add ``pytest-asyncio``.

|| Qué corrida gana y qué rechaza la base. La regla de precedencia ES el
change: la selección le gana al default de configuración, el default nunca se
escribe como fila, y «la más reciente» nunca es una respuesta. Más el único
invariante que NO está en Python: a lo sumo una corrida activa por cliente,
garantizado por un índice parcial único. Contra un Postgres real, en un esquema
descartable, con la plomería async a mano — igual que el vecino, y por lo mismo:
un índice parcial es comportamiento de la base y un doble testearía el doble.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.domain.business_db_store import (
    BusinessDbSelectionRow,
    BusinessDbStampRow,
    MirrorRun,
    RunNotLoaded,
    activate_run,
    get_stamp,
    record_stamp,
    resolve_active_run,
)
from app.foundation.persistence.database import Base, to_async_url, to_sync_url

pytestmark = pytest.mark.integration

TEST_SCHEMA = "business_db_tests"
TENANT = "test_business_db"


def _unreachable_reason(url: str) -> str | None:
    """Why the database cannot be used, or ``None`` if it can.

    || Por qué no se puede usar la base, o ``None`` si sí se puede.
    """
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return f"no reachable Postgres at {url.rsplit('@', 1)[-1]} ({type(error).__name__})"
    return None


@pytest.fixture(scope="module")
def test_schema() -> Iterator[str]:
    """Create the throwaway schema and the two tables, ONCE for the module.

    Module-scoped for the reason the neighbour measured: against a managed
    Postgres over the internet a single connect costs seconds, so a per-test
    schema would spend minutes preparing and seconds testing.

    || Crea el esquema descartable y las dos tablas UNA vez por módulo.
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
        # checkfirst=False for the same reason as the neighbours: with a
        # search_path set, the existence check can resolve to a table in
        # `public` and skip creating the test one.
        # || checkfirst=False por lo mismo que los vecinos: con search_path
        # puesto, el chequeo puede resolver a una tabla de `public`.
        connection.execute(text(f"SET search_path TO {TEST_SCHEMA},public"))
        Base.metadata.create_all(
            connection,
            tables=[BusinessDbSelectionRow.__table__, BusinessDbStampRow.__table__],
            checkfirst=False,
        )
        connection.commit()

    yield TEST_SCHEMA

    with setup_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.commit()
    setup_engine.dispose()


@pytest.fixture
def run_with(test_schema: str) -> Callable[[Callable[[AsyncSession], Awaitable[Any]]], Any]:
    """Run one coroutine against empty selection and stamp tables.

    Emptied before each scenario rather than rebuilt, so order never matters
    and the cost per test is two DELETEs.

    || Corre una corutina contra las dos tablas vacías. Se vacían antes de cada
    escenario en vez de reconstruirse, así el orden nunca importa.
    """
    settings = get_settings()

    def _run(scenario: Callable[[AsyncSession], Awaitable[Any]]) -> Any:
        async def _main() -> Any:
            # `to_async_url`, not the raw setting: `DATABASE_URL` may carry no
            # driver token, and `create_async_engine` on a bare `postgresql://`
            # picks a SYNC dialect and dies importing psycopg2.
            # || `to_async_url` y no el setting crudo.
            engine = create_async_engine(
                to_async_url(settings.DATABASE_URL),
                connect_args={"server_settings": {"search_path": f"{test_schema},public"}},
            )
            try:
                factory = async_sessionmaker(engine, expire_on_commit=False)
                async with factory() as session:
                    await session.execute(delete(BusinessDbSelectionRow))
                    await session.execute(delete(BusinessDbStampRow))
                    await session.commit()
                    return await scenario(session)
            finally:
                await engine.dispose()

        return asyncio.run(_main())

    return _run


def _settings(run_id: str = "", env: str = "PROD") -> Settings:
    """Settings with only what the resolver reads. || Solo lo que lee el resolver."""
    return Settings(
        _env_file=None,
        TENANT_ID=TENANT,
        BUSINESS_DB_RUN_ID=run_id,
        BUSINESS_DB_ENV=env,
    )


def _run_row(run_id: str, *, env: str = "PROD", loaded_data: bool = True) -> MirrorRun:
    return MirrorRun(
        tenant=TENANT,
        env=env,
        run_id=run_id,
        extractor_version="1.0.0",
        created_at_utc=datetime(2026, 9, 9, tzinfo=UTC),
        status="complete",
        loaded_metadata=True,
        loaded_dependencies=True,
        loaded_data=loaded_data,
        manifest_sha256="deadbeef",
    )


async def _count_selections(session: AsyncSession) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(BusinessDbSelectionRow)
        .where(BusinessDbSelectionRow.tenant_id == TENANT)
    )


def test_the_selection_beats_the_configured_default(run_with):
    """Quien opera el producto está por encima de quien lo despliega."""

    async def scenario(session: AsyncSession):
        await activate_run(session, tenant_id=TENANT, run=_run_row("selected_run"))
        await session.commit()
        return await resolve_active_run(session, _settings(run_id="configured_run"), TENANT)

    active = run_with(scenario)
    assert active.run_id == "selected_run"
    assert active.origin == "selected"


def test_without_a_selection_the_configuration_wins_as_default(run_with):
    """Una instalación nueva arranca funcionando sin que nadie entre a la consola."""

    async def scenario(session: AsyncSession):
        return await resolve_active_run(session, _settings(run_id="configured_run"), TENANT)

    active = run_with(scenario)
    assert active.run_id == "configured_run"
    assert active.origin == "default"
    # Sin `activated_at` ni `activated_by`: nadie activó nada.
    assert active.activated_at is None
    assert active.activated_by is None


def test_with_neither_there_is_no_run_and_a_reason(run_with):
    """Nunca «la más reciente»: se dice que no hay, y por qué."""

    async def scenario(session: AsyncSession):
        return await resolve_active_run(session, _settings(run_id=""), TENANT)

    active = run_with(scenario)
    assert active.run_id is None
    assert active.origin == "none"
    assert not active.resolved
    assert active.reason and "BUSINESS_DB_RUN_ID" in active.reason


def test_resolving_by_default_writes_no_row(run_with):
    """La semilla NO se materializa.

    Una fila haría parecer que alguien eligió esa corrida, y después no habría
    forma de distinguir «el default» de «lo que eligió alguien».
    """

    async def scenario(session: AsyncSession):
        await resolve_active_run(session, _settings(run_id="configured_run"), TENANT)
        await resolve_active_run(session, _settings(run_id="configured_run"), TENANT)
        await session.commit()
        return await _count_selections(session)

    assert run_with(scenario) == 0


def test_activating_retires_the_previous_one(run_with):
    async def scenario(session: AsyncSession):
        await activate_run(session, tenant_id=TENANT, run=_run_row("first"))
        await session.commit()
        await activate_run(session, tenant_id=TENANT, run=_run_row("second"))
        await session.commit()
        result = await session.execute(
            select(BusinessDbSelectionRow)
            .where(BusinessDbSelectionRow.tenant_id == TENANT)
            .order_by(BusinessDbSelectionRow.run_id)
        )
        return [(row.run_id, row.status) for row in result.scalars()]

    rows = run_with(scenario)
    assert dict(rows) == {"first": "retired", "second": "active"}
    # La anterior queda como historial y no borrada: qué corridas estuvieron
    # activas es el único registro de una decisión que cambia cada respuesta.
    assert len(rows) == 2


def test_reactivating_a_retired_run_reuses_its_row(run_with):
    """Elegir, retirar y volver a elegir es la MISMA fila (tenant, env, run)."""

    async def scenario(session: AsyncSession):
        for run_id in ("first", "second", "first"):
            await activate_run(session, tenant_id=TENANT, run=_run_row(run_id))
            await session.commit()
        count = await _count_selections(session)
        active = await resolve_active_run(session, _settings(), TENANT)
        return count, active

    count, active = run_with(scenario)
    assert count == 2, "no se crea una fila nueva por reactivar"
    assert active.run_id == "first"


def test_a_run_without_data_is_refused(run_with):
    """El árbol sale de `business_data`: activarla dejaría todo sin resolver."""

    async def scenario(session: AsyncSession):
        with pytest.raises(RunNotLoaded) as raised:
            await activate_run(
                session, tenant_id=TENANT, run=_run_row("empty", loaded_data=False)
            )
        return str(raised.value)

    assert "loaded_data" in run_with(scenario)


def test_a_refused_activation_leaves_the_previous_selection_alone(run_with):
    async def scenario(session: AsyncSession):
        await activate_run(session, tenant_id=TENANT, run=_run_row("good"))
        await session.commit()
        with pytest.raises(RunNotLoaded):
            await activate_run(
                session, tenant_id=TENANT, run=_run_row("empty", loaded_data=False)
            )
        await session.rollback()
        return await resolve_active_run(session, _settings(), TENANT)

    active = run_with(scenario)
    assert active.run_id == "good"
    assert active.origin == "selected"


def test_activated_by_is_stored_as_declared_and_never_invented(run_with):
    async def scenario(session: AsyncSession):
        with_author = await activate_run(
            session, tenant_id=TENANT, run=_run_row("with_author"), activated_by="cristian"
        )
        await session.commit()
        without = await activate_run(session, tenant_id=TENANT, run=_run_row("no_author"))
        await session.commit()
        return with_author.activated_by, without.activated_by

    declared, absent = run_with(scenario)
    assert declared == "cristian"
    # Ausente, no `"unknown"`: un autor inventado se leería como un registro.
    assert absent is None


def test_two_active_runs_for_one_tenant_are_impossible(run_with):
    """El invariante lo garantiza la BASE, no el código.

    La misma regla sostenida solo en la aplicación se rompe con dos procesos
    concurrentes, así que esto inserta a mano —salteando `activate_run`, que
    retira la anterior— y espera que falle el índice parcial.
    """

    async def scenario(session: AsyncSession):
        session.add(
            BusinessDbSelectionRow(tenant_id=TENANT, env="PROD", run_id="one", status="active")
        )
        session.add(
            BusinessDbSelectionRow(tenant_id=TENANT, env="PROD", run_id="two", status="active")
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        return True

    assert run_with(scenario)


def test_one_active_and_many_retired_are_fine(run_with):
    """El índice es PARCIAL: solo restringe las activas."""

    async def scenario(session: AsyncSession):
        session.add(
            BusinessDbSelectionRow(tenant_id=TENANT, env="PROD", run_id="one", status="active")
        )
        session.add(
            BusinessDbSelectionRow(tenant_id=TENANT, env="PROD", run_id="two", status="retired")
        )
        session.add(
            BusinessDbSelectionRow(tenant_id=TENANT, env="DEV", run_id="three", status="retired")
        )
        await session.commit()
        return await resolve_active_run(session, _settings(), TENANT)

    assert run_with(scenario).run_id == "one"


def test_the_stamp_records_its_run_and_a_re_stamp_replaces_it(run_with):
    """Solo hay un estado estampado por versión del corpus."""

    async def scenario(session: AsyncSession):
        await record_stamp(
            session,
            tenant_id=TENANT,
            doc_version="v1",
            env="PROD",
            run_id="first",
            rows_updated=10,
        )
        await session.commit()
        await record_stamp(
            session,
            tenant_id=TENANT,
            doc_version="v1",
            env="PROD",
            run_id="second",
            rows_updated=56537,
        )
        await session.commit()
        return await get_stamp(session, TENANT, "v1")

    stamp = run_with(scenario)
    assert stamp is not None
    assert stamp.run_id == "second"
    assert stamp.rows_updated == 56537


def test_zero_rows_updated_is_recorded_not_treated_as_a_failure(run_with):
    """Cero es una respuesta real: el corpus no tenía nada que estampar."""

    async def scenario(session: AsyncSession):
        await record_stamp(
            session, tenant_id=TENANT, doc_version="v0", env="PROD", run_id="r", rows_updated=0
        )
        await session.commit()
        return await get_stamp(session, TENANT, "v0")

    stamp = run_with(scenario)
    assert stamp is not None
    assert stamp.rows_updated == 0
