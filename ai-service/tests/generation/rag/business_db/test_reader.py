"""SQL against jsonb, on a throwaway schema. An in-memory double would test the double.

|| SQL sobre jsonb, en un esquema descartable. Un doble en memoria testearía el doble.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.foundation.persistence.database import to_sync_url
from app.generation.rag.business_db.reader import (
    clear_reader_cache,
    read_catalog_rows,
    read_run_created_at,
    read_table_dictionary,
)

pytestmark = pytest.mark.integration

SCHEMA = "business_db_context_reader"
TENANT = "test_reader"
ENV = "PROD"
RUN = "reader_run"


def _unreachable_reason(url: str) -> str | None:
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return f"no reachable Postgres at {url.rsplit('@', 1)[-1]} ({type(error).__name__})"
    return None


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    settings = get_settings()
    sync_url = to_sync_url(settings.DATABASE_URL)
    reason = _unreachable_reason(sync_url)
    if reason is not None:
        pytest.skip(f"integration test needs a database: {reason}")

    engine = create_engine(sync_url, connect_args={"connect_timeout": 30})
    with engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(
            text(
                f"""
                CREATE TABLE {SCHEMA}.extraction_runs (
                    tenant text, env text, run_id text, created_at_utc timestamptz
                )
                """
            )
        )
        connection.execute(
            text(
                f"""
                CREATE TABLE {SCHEMA}.business_tables (
                    tenant text, env text, run_id text, name text,
                    description_es text, description_en text, columns jsonb
                )
                """
            )
        )
        connection.execute(
            text(
                f"""
                CREATE TABLE {SCHEMA}.business_data (
                    tenant text, env text, run_id text, table_name text, row jsonb
                )
                """
            )
        )
        connection.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.extraction_runs
                VALUES (:tenant, :env, :run_id, :created)
                """
            ),
            {
                "tenant": TENANT,
                "env": ENV,
                "run_id": RUN,
                "created": datetime(2026, 9, 9, 21, 49, 21, tzinfo=UTC),
            },
        )
        connection.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.business_tables
                VALUES (:tenant, :env, :run_id, 'TABLE7', 'Bancos', 'Banks',
                        '[{{"name": "NCODE", "description": "Código"}},
                          {{"name": "SSTATREGT", "description": "Estado según tabla 26"}}]'::jsonb)
                """
            ),
            {"tenant": TENANT, "env": ENV, "run_id": RUN},
        )
        connection.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.business_tables
                VALUES (:tenant, :env, :run_id, 'TABLE_NULL', 'Sin columnas', NULL, NULL)
                """
            ),
            {"tenant": TENANT, "env": ENV, "run_id": RUN},
        )
        for index in range(5):
            connection.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA}.business_data
                    VALUES (:tenant, :env, :run_id, 'TABLE7',
                            jsonb_build_object('NCODE', CAST(:code AS text), 'SSTATREGT', '1'))
                    """
                ),
                {"tenant": TENANT, "env": ENV, "run_id": RUN, "code": str(index)},
            )
        connection.commit()

    clear_reader_cache()
    yield settings.DATABASE_URL
    clear_reader_cache()
    with engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.commit()
    engine.dispose()


def test_dictionary_filters_by_the_run(database_url):
    found = read_table_dictionary(database_url, TENANT, ENV, RUN, "TABLE7", schema=SCHEMA)
    missing = read_table_dictionary(
        database_url, TENANT, ENV, "other_run", "TABLE7", schema=SCHEMA
    )

    assert found is not None
    assert found.description_es == "Bancos"
    assert [column.name for column in found.columns or []] == ["NCODE", "SSTATREGT"]
    assert missing is None


def test_null_columns_stay_none(database_url):
    found = read_table_dictionary(
        database_url, TENANT, ENV, RUN, "TABLE_NULL", schema=SCHEMA
    )
    assert found is not None
    assert found.columns is None


def test_limit_plus_one_detects_overflow(database_url):
    rows, capped = read_catalog_rows(
        database_url, TENANT, ENV, RUN, "TABLE7", limit=3, schema=SCHEMA
    )
    assert len(rows) == 3
    assert capped is True


def test_empty_table_is_not_an_empty_catalog(database_url):
    rows, capped = read_catalog_rows(
        database_url, TENANT, ENV, RUN, "TABLE99", limit=10, schema=SCHEMA
    )
    assert rows == ()
    assert capped is False


def test_run_created_at_is_the_extractor_clock(database_url):
    created = read_run_created_at(database_url, TENANT, ENV, RUN, schema=SCHEMA)
    assert created is not None
    assert created.year == 2026
    assert created.month == 9
    assert created.day == 9
