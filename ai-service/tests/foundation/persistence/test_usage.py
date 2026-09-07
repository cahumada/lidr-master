"""RecordingLLM against a store double; UsageStore against Postgres or a skip.

|| RecordingLLM contra un doble del store; UsageStore contra Postgres o un skip.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.foundation.llm.wrapper import Completion, LLMError, Usage
from app.foundation.persistence.database import Base, to_async_url, to_sync_url
from app.foundation.persistence.usage import (
    LlmUsageEventRow,
    RecordingLLM,
    UsageStore,
)

TEST_SCHEMA = "llm_usage_tests"


class FakeInner:
    model = "gpt-4o-mini"

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str) -> Completion:
        self.calls.append({"system": system, "user": user})
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeStore:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.error: Exception | None = None

    def record(self, **kwargs) -> None:
        if self.error is not None:
            raise self.error
        self.records.append(kwargs)


def _usage(*, incoming: int = 100, outgoing: int = 40) -> Usage:
    return Usage(
        input_tokens=incoming,
        output_tokens=outgoing,
        total_tokens=incoming + outgoing,
        reported=True,
    )


def _completion(text: str = "respuesta", usage: Usage | None = None) -> Completion:
    return Completion(text=text, usage=usage or _usage())


class TestRecordingLLM:
    def test_a_successful_complete_is_recorded(self):
        store = FakeStore()
        inner = FakeInner([_completion()])
        llm = RecordingLLM(
            inner,
            store,
            purpose="answer",
            provider_id="openai",
            tenant_id="t1",
            session_id=None,
            thread_id=None,
        )

        completion = llm.complete(system="s", user="u")

        assert completion.text == "respuesta"
        assert len(store.records) == 1
        row = store.records[0]
        assert row["purpose"] == "answer"
        assert row["provider_id"] == "openai"
        assert row["model"] == "gpt-4o-mini"
        assert row["tenant_id"] == "t1"
        assert row["usage"].total_tokens == 140
        assert row["session_id"] is None
        assert row["thread_id"] is None

    def test_an_llm_error_writes_no_row(self):
        store = FakeStore()
        inner = FakeInner([LLMError("empty content")])
        llm = RecordingLLM(
            inner, store, purpose="answer", provider_id="openai", tenant_id="t1"
        )

        with pytest.raises(LLMError, match="empty content"):
            llm.complete(system="s", user="u")

        assert store.records == []

    def test_a_store_failure_still_returns_the_completion(self):
        store = FakeStore()
        store.error = RuntimeError("insert failed")
        inner = FakeInner([_completion(text="igual sirve")])
        llm = RecordingLLM(
            inner, store, purpose="answer_synthesizer", provider_id="openai", tenant_id="t1"
        )

        completion = llm.complete(system="s", user="u")

        assert completion.text == "igual sirve"
        assert completion.usage.reported is True


def _unreachable_reason(url: str) -> str | None:
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return f"no reachable Postgres at {url.rsplit('@', 1)[-1]} ({type(error).__name__})"
    return None


@pytest.fixture(scope="session")
def test_schema() -> Iterator[str]:
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
        connection.execute(text(f"SET search_path TO {TEST_SCHEMA},public"))
        Base.metadata.create_all(
            connection, tables=[LlmUsageEventRow.__table__], checkfirst=False
        )
        connection.commit()

    yield TEST_SCHEMA

    with setup_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        connection.commit()
    setup_engine.dispose()


@pytest.fixture
def run_with_store(
    test_schema: str,
) -> Callable[[Callable[[UsageStore], Awaitable[Any]]], Any]:
    settings = get_settings()

    def _run(scenario: Callable[[UsageStore], Awaitable[Any]]) -> Any:
        async def _main() -> Any:
            engine = create_async_engine(
                to_async_url(settings.DATABASE_URL),
                connect_args={"server_settings": {"search_path": f"{test_schema},public"}},
            )
            sync_engine = create_engine(
                to_sync_url(settings.DATABASE_URL),
                connect_args={"options": f"-csearch_path={test_schema},public"},
            )
            try:
                factory = async_sessionmaker(engine, expire_on_commit=False)
                sync_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)
                async with factory() as session:
                    await session.execute(delete(LlmUsageEventRow))
                    await session.commit()
                    store = UsageStore(session, sync_session_factory=sync_factory)
                    return await scenario(store)
            finally:
                await engine.dispose()
                sync_engine.dispose()

        return asyncio.run(_main())

    return _run


def test_record_then_summarize_totals_by_model(run_with_store):
    async def scenario(store: UsageStore):
        store.record(
            tenant_id="acme",
            purpose="answer",
            provider_id="openai",
            model="gpt-4o-mini",
            usage=_usage(incoming=100, outgoing=40),
        )
        store.record(
            tenant_id="acme",
            purpose="answer",
            provider_id="openai",
            model="gpt-4o-mini",
            usage=_usage(incoming=100, outgoing=40),
        )
        store.record(
            tenant_id="other",
            purpose="answer",
            provider_id="openai",
            model="gpt-4o-mini",
            usage=_usage(incoming=999, outgoing=999),
        )

        totals = await store.summarize("acme")

        assert totals.total_calls == 2
        assert totals.input_tokens == 200
        assert totals.output_tokens == 80
        assert totals.total_tokens == 280
        assert len(totals.by_model) == 1
        assert totals.by_model[0].provider_id == "openai"
        assert totals.by_model[0].model == "gpt-4o-mini"
        assert totals.by_model[0].calls == 2

    run_with_store(scenario)


def test_summarize_filters_session_and_purpose(run_with_store):
    async def scenario(store: UsageStore):
        session_id = str(uuid4())
        store.record(
            tenant_id="acme",
            purpose="answer_synthesizer",
            provider_id="openai",
            model="gpt-4o-mini",
            usage=_usage(incoming=10, outgoing=5),
            session_id=session_id,
            thread_id="th-1",
        )
        store.record(
            tenant_id="acme",
            purpose="answer",
            provider_id="openai",
            model="gpt-4o-mini",
            usage=_usage(incoming=50, outgoing=20),
        )

        by_session = await store.summarize("acme", session_id=session_id)
        assert by_session.total_calls == 1
        assert by_session.total_tokens == 15

        by_purpose = await store.summarize("acme", purpose="answer")
        assert by_purpose.total_calls == 1
        assert by_purpose.total_tokens == 70

    run_with_store(scenario)


def test_summarize_empty_window_is_zeros(run_with_store):
    async def scenario(store: UsageStore):
        future = datetime.now(UTC) + timedelta(days=1)
        totals = await store.summarize("acme", since=future)

        assert totals.total_calls == 0
        assert totals.input_tokens == 0
        assert totals.by_model == []

    run_with_store(scenario)
