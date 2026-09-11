"""Retention, isolation, and that an audit trail never costs an answer.

|| Retención, aislamiento, y que la auditoría nunca cueste una respuesta.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.foundation.persistence.database import Base, to_sync_url
from app.foundation.persistence.prompts import (
    AnswerPromptRow,
    read_prompt,
    save_prompt,
)

TENANT = "life_seguros"
OTHER = "otro_tenant"
TEST_SCHEMA = "answer_prompt_tests"


def _unreachable_reason(url: str) -> str | None:
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect():
            pass
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return f"no reachable Postgres at {url.rsplit('@', 1)[-1]} ({type(error).__name__})"
    return None


@pytest.fixture(scope="module")
def factory():
    """Postgres or a skip, like the usage tests next door.

    The retention window is a comparison between an aware Python datetime and a
    ``TIMESTAMP WITH TIME ZONE`` column. SQLite hands those back naive, so a
    test on it would be testing the wrong dialect -- and passing a portability
    layer for a database we never deploy is the empty abstraction the standards
    turn down.

    || Postgres o un skip, como los tests de uso de al lado. La ventana es una
    comparación con una columna con timezone, y SQLite las devuelve naive.
    """
    sync_url = to_sync_url(get_settings().DATABASE_URL)
    reason = _unreachable_reason(sync_url)
    if reason is not None:
        pytest.skip(f"integration test needs a database: {reason}.")

    engine = create_engine(sync_url, connect_args={"connect_timeout": 30})
    with engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        connection.commit()
    scoped = engine.execution_options(
        schema_translate_map={None: TEST_SCHEMA}
    )
    with scoped.connect() as connection:
        Base.metadata.create_all(
            connection, tables=[AnswerPromptRow.__table__], checkfirst=False
        )
        connection.commit()

    yield sessionmaker(scoped)

    with engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.commit()
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean(factory):
    with factory() as session:
        session.execute(delete(AnswerPromptRow))
        session.commit()


def _save(factory, *, tenant: str = TENANT, retention_days: int = 7, **kwargs) -> str | None:
    return save_prompt(
        tenant_id=tenant,
        agent="answer_synthesizer",
        model="claude-opus-5",
        system_text="sistema",
        user_text="usuario",
        context_budget=16384,
        retention_days=retention_days,
        session_factory=factory,
        **kwargs,
    )


def _age(factory, prompt_id: str, days: int) -> None:
    with factory() as session:
        row = session.get(AnswerPromptRow, prompt_id)
        row.created_at = datetime.now(UTC) - timedelta(days=days)
        session.commit()


class TestRoundTrip:
    def test_what_was_sent_comes_back_verbatim(self, factory) -> None:
        prompt_id = save_prompt(
            tenant_id=TENANT,
            agent="answer",
            model="claude-opus-5",
            system_text="Sos un analista. **literal**",
            user_text="Pregunta:\n¿qué valida CA014?",
            context_budget=16384,
            retention_days=7,
            session_factory=factory,
        )
        stored = read_prompt(
            prompt_id, tenant_id=TENANT, retention_days=7, session_factory=factory
        )

        assert stored is not None
        assert stored.system_text == "Sos un analista. **literal**"
        assert stored.user_text == "Pregunta:\n¿qué valida CA014?"
        assert stored.context_budget == 16384

    def test_the_profile_travels_when_there_is_one(self, factory) -> None:
        prompt_id = _save(factory, profile_id="conservador")
        stored = read_prompt(
            prompt_id, tenant_id=TENANT, retention_days=7, session_factory=factory
        )
        assert stored.profile_id == "conservador"


class TestRetention:
    def test_the_sweep_rides_along_with_the_write(self, factory) -> None:
        old = _save(factory)
        _age(factory, old, days=8)

        _save(factory)  # any write sweeps

        assert read_prompt(
            old, tenant_id=TENANT, retention_days=7, session_factory=factory
        ) is None

    def test_a_row_inside_the_window_survives(self, factory) -> None:
        kept = _save(factory)
        _age(factory, kept, days=6)

        _save(factory)

        assert read_prompt(
            kept, tenant_id=TENANT, retention_days=7, session_factory=factory
        ) is not None

    def test_the_window_is_rechecked_on_read(self, factory) -> None:
        # A row that outlived a sweep which did not run is still expired.
        # Otherwise the retention promise would depend on write traffic.
        # || Una fila que sobrevivió a un barrido que no corrió está vencida.
        prompt_id = _save(factory)
        _age(factory, prompt_id, days=30)

        assert read_prompt(
            prompt_id, tenant_id=TENANT, retention_days=7, session_factory=factory
        ) is None

    def test_the_window_is_configurable(self, factory) -> None:
        prompt_id = _save(factory)
        _age(factory, prompt_id, days=10)

        assert read_prompt(
            prompt_id, tenant_id=TENANT, retention_days=30, session_factory=factory
        ) is not None

    def test_the_sweep_does_not_cross_tenants(self, factory) -> None:
        theirs = _save(factory, tenant=OTHER)
        _age(factory, theirs, days=90)

        _save(factory, tenant=TENANT)

        assert read_prompt(
            theirs, tenant_id=OTHER, retention_days=365, session_factory=factory
        ) is not None


class TestFailureIsNotFatal:
    def test_a_write_that_fails_returns_none_instead_of_raising(self) -> None:
        # Runs right after a 40-50s completion the user is waiting on: losing
        # the audit trail is a bad turn, losing the answer is a broken one.
        # || Perder la auditoría es un turno malo; perder la respuesta, roto.
        class Exploding:
            def __call__(self):
                raise RuntimeError("no database")

        assert _save(Exploding()) is None


class TestIsolationFromUsage:
    def test_a_prompt_row_is_not_a_usage_row(self, factory) -> None:
        from app.foundation.persistence.usage import LlmUsageEventRow

        assert AnswerPromptRow.__tablename__ != LlmUsageEventRow.__tablename__

    def test_the_text_columns_live_only_on_the_prompt_table(self) -> None:
        from app.foundation.persistence.usage import LlmUsageEventRow

        usage_columns = set(LlmUsageEventRow.__table__.columns.keys())
        assert "system_text" not in usage_columns
        assert "user_text" not in usage_columns


def test_a_missing_id_reads_as_none(factory) -> None:
    assert read_prompt(
        "no-existe", tenant_id=TENANT, retention_days=7, session_factory=factory
    ) is None


def test_another_tenants_id_is_not_readable(factory) -> None:
    theirs = _save(factory, tenant=OTHER)

    assert read_prompt(
        theirs, tenant_id=TENANT, retention_days=7, session_factory=factory
    ) is None
