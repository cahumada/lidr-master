"""Three cases against the real `20260909_214921` run, when it is loaded.

If a case is missing that is a finding, not a skipped test to forget.

|| Tres casos contra la corrida real `20260909_214921`, cuando está cargada.
Si un caso no aparece, eso es un hallazgo.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.foundation.persistence.database import to_sync_url
from app.generation.rag.business_db.reader import (
    _parse_columns,
    read_catalog_rows,
    read_table_dictionary,
)
from app.generation.rag.business_db.resolve import resolve_context
from app.generation.rag.business_db.validity import (
    column_description,
    status_catalog_is_foreign,
    status_catalog_is_table26,
)
from app.generation.rag.navigation import load_navigation_tree_from_database_url

pytestmark = pytest.mark.integration

RUN_ID = "20260909_214921"
ENV = "PROD"
TENANT = "life_seguros"


def _reachable(url: str) -> str | None:
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as error:  # noqa: BLE001 -- the reason is the point
        return str(error)
    return None


@pytest.fixture(scope="module")
def real_run():
    settings = get_settings()
    url = to_sync_url(settings.DATABASE_URL)
    reason = _reachable(url)
    if reason:
        pytest.skip(f"no reachable Postgres: {reason}")

    engine = create_engine(url, connect_args={"connect_timeout": 20})
    with engine.connect() as connection:
        count = connection.execute(
            text(
                """
                SELECT count(1) FROM visualtime.business_data
                WHERE tenant = :tenant AND env = :env AND run_id = :run_id
                  AND table_name = 'WINDOWS'
                """
            ),
            {"tenant": TENANT, "env": ENV, "run_id": RUN_ID},
        ).scalar()
    if not count:
        engine.dispose()
        pytest.skip(
            f"run {RUN_ID} is not loaded for {TENANT}/{ENV}; "
            "the three cases cannot be measured."
        )
    tree = load_navigation_tree_from_database_url(
        settings.DATABASE_URL, tenant=TENANT, env=ENV, run_id=RUN_ID
    )
    yield settings, tree, engine
    engine.dispose()


def test_type_10_resolves_to_its_table_with_valid_rows(real_run):
    settings, tree, _engine = real_run
    code = "MA0007"
    assert tree.window_type(code) == "10"
    assert tree.ng_identi(code)

    context = resolve_context(
        database_url=settings.DATABASE_URL,
        tenant=TENANT,
        env=ENV,
        run_id=RUN_ID,
        codes=[code],
        tree=tree,
        max_rows=settings.BUSINESS_DB_CONTEXT_MAX_ROWS,
    )
    resolution = context.resolutions[0]
    assert resolution.table_name == f"TABLE{tree.ng_identi(code)}"
    assert resolution.rows_valid >= 1 or resolution.outcome in {
        "table_not_loaded",
        "table_not_in_dictionary",
    }


def test_another_type_with_ng_identi_is_ignored(real_run):
    settings, tree, _engine = real_run
    # COL504 is the documented counter-example (§7.1): type 3, NG_IDENTI=2.
    # || COL504 es el contraejemplo documentado.
    code = "COL504"
    if tree.window_type(code) == "10" or not tree.ng_identi(code):
        pytest.fail(
            f"{code} is no longer the type-3 NG_IDENTI counter-example "
            f"(type={tree.window_type(code)}, ng_identi={tree.ng_identi(code)}). "
            "That is a finding for domain §7.1."
        )

    context = resolve_context(
        database_url=settings.DATABASE_URL,
        tenant=TENANT,
        env=ENV,
        run_id=RUN_ID,
        codes=[code],
        tree=tree,
        max_rows=10,
    )
    assert context.resolutions[0].outcome == "ng_identi_ignored_by_type"
    assert context.complete is True


def test_an_unloaded_table_is_reported(real_run):
    settings, tree, engine = real_run
    wanted = []
    for code in tree.codes():
        if tree.window_type(code) != "10":
            continue
        ident = tree.ng_identi(code)
        if ident:
            wanted.append((code, f"TABLE{ident}"))
    names = sorted({table for _code, table in wanted})
    with engine.connect() as connection:
        in_dictionary = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT name FROM visualtime.business_tables
                    WHERE tenant = :tenant AND env = :env AND run_id = :run_id
                      AND name = ANY(:names)
                    """
                ),
                {"tenant": TENANT, "env": ENV, "run_id": RUN_ID, "names": names},
            )
        }
        loaded = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT DISTINCT table_name FROM visualtime.business_data
                    WHERE tenant = :tenant AND env = :env AND run_id = :run_id
                      AND table_name = ANY(:names)
                    """
                ),
                {"tenant": TENANT, "env": ENV, "run_id": RUN_ID, "names": names},
            )
        }

    missing = None
    for code, table in wanted:
        if table not in in_dictionary:
            missing = (code, table, "table_not_in_dictionary")
            break
        if table not in loaded:
            missing = (code, table, "table_not_loaded")
            break

    if missing is None:
        pytest.fail(
            "every type-10 TABLE<n> in this run has dictionary and rows; "
            "the unloaded-table case is gone — that is a finding for §13.2."
        )

    code, table, expected = missing
    context = resolve_context(
        database_url=settings.DATABASE_URL,
        tenant=TENANT,
        env=ENV,
        run_id=RUN_ID,
        codes=[code],
        tree=tree,
        max_rows=10,
    )
    assert context.resolutions[0].outcome == expected
    assert context.resolutions[0].table_name == table
    assert context.complete is False


def test_sstatregt_catalogs_of_table_n(real_run):
    """Task 3.6: how many TABLE<n> remits to TABLE26, another catalog, or none.

    || Task 3.6: cuántas TABLE<n> remiten a TABLE26, a otro catálogo, o a ninguno.
    """
    _settings, tree, engine = real_run
    wanted = {
        f"TABLE{ident}"
        for code in tree.codes()
        if tree.window_type(code) == "10" and (ident := tree.ng_identi(code))
    }
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT name, columns FROM visualtime.business_tables
                WHERE tenant = :tenant AND env = :env AND run_id = :run_id
                  AND name = ANY(:names)
                """
            ),
            {
                "tenant": TENANT,
                "env": ENV,
                "run_id": RUN_ID,
                "names": sorted(wanted),
            },
        ).all()

    by_name = {name: _parse_columns(columns) for name, columns in rows}
    table26 = 0
    foreign = 0
    generic = 0
    missing = 0
    foreign_names: list[str] = []
    for table in wanted:
        columns = by_name.get(table)
        if columns is None:
            missing += 1
            continue
        description = column_description(columns, "SSTATREGT")
        if status_catalog_is_table26(description):
            table26 += 1
        elif status_catalog_is_foreign(description):
            foreign += 1
            foreign_names.append(table)
        else:
            generic += 1

    # The numbers go into tasks.md 3.6. They are the measurement.
    # || Los números van a tasks.md 3.6. Son la medición.
    assert table26 + foreign + generic + missing == len(wanted)
    assert wanted, "the run has no type-10 TABLE<n>"
    print(
        f"SSTATREGT catalogs TABLE<n>: table26={table26} foreign={foreign} "
        f"generic={generic} missing={missing} foreign_names={sorted(foreign_names)}"
    )
    # Keep the unused reader import honest: one table still goes through it.
    # || Una tabla todavía pasa por el reader, para no dejar el import muerto.
    assert read_table_dictionary(
        get_settings().DATABASE_URL, TENANT, ENV, RUN_ID, "TABLE7"
    ) is not None
    rows, _capped = read_catalog_rows(
        get_settings().DATABASE_URL, TENANT, ENV, RUN_ID, "TABLE7", 1
    )
    assert rows
