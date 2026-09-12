"""Read-only queries against the VisualTIME mirror.

Cached by `(env, run_id, table_name)`, same shape as
`get_navigation_tree_for_run`. Nothing here writes `visualtime.*`.

SQL filters by `(tenant, env, run_id, table_name)` and applies
`LIMIT cap + 1` — the extra row is how `rows_capped` is detected. The
validity predicate is evaluated in Python because dates live in jsonb as
undeclared text.

|| Consultas de solo lectura contra el mirror. Cacheadas por
`(env, run_id, table_name)`. Nada acá escribe `visualtime.*`.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

import structlog

from app.generation.rag.business_db.models import (
    CatalogRow,
    ColumnDictionary,
    DependencyTable,
    DictionaryColumn,
    DictionaryForeignKey,
    DictionaryIndex,
    TableDictionary,
    TableDictionaryDetail,
)

log = structlog.get_logger()

_DEFAULT_SCHEMA = "visualtime"


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://")


def _parse_columns(raw: Any) -> list[ColumnDictionary] | None:
    """`None` stays `None`; anything else becomes a (possibly empty) list.

    || `None` se queda `None`; cualquier otra cosa es una lista (quizá vacía).
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        parsed: list[ColumnDictionary] = []
        for name, body in raw.items():
            if isinstance(body, dict):
                parsed.append(
                    ColumnDictionary(
                        name=str(name),
                        description=_column_description(body),
                    )
                )
            else:
                parsed.append(ColumnDictionary(name=str(name)))
        return parsed
    if isinstance(raw, list):
        parsed = []
        for item in raw:
            if isinstance(item, str):
                parsed.append(ColumnDictionary(name=item))
                continue
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("column_name") or item.get("columnName")
            if not name:
                continue
            parsed.append(
                ColumnDictionary(name=str(name), description=_column_description(item))
            )
        return parsed
    return None


def _column_description(body: dict) -> str | None:
    for key in (
        "descriptionEs",
        "description_es",
        "descriptionEn",
        "description_en",
        "description",
        "comment",
        "remarks",
        "column_comment",
    ):
        value = body.get(key)
        if value:
            return str(value)
    return None


def _row_values(raw: Any) -> dict[str, str | None]:
    if not isinstance(raw, dict):
        return {}
    values: dict[str, str | None] = {}
    for key, value in raw.items():
        if value is None:
            values[str(key)] = None
        elif isinstance(value, (dict, list)):
            values[str(key)] = str(value)
        else:
            values[str(key)] = str(value)
    return values


@lru_cache(maxsize=256)
def read_table_dictionary(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    table_name: str,
    schema: str = _DEFAULT_SCHEMA,
) -> TableDictionary | None:
    """One `business_tables` row, or ``None`` when the run does not have it.

    || Una fila de `business_tables`, o ``None`` si la corrida no la tiene.
    """
    import psycopg
    from psycopg.rows import dict_row

    # The mirror names the table `name` here and `table_name` on
    # `business_data`. Same object, two column names — the query says so.
    # || El mirror llama `name` a la tabla acá y `table_name` en
    # `business_data`. El mismo objeto, dos columnas.
    sql = f"""
        SELECT name, description_es, description_en, columns
        FROM {schema}.business_tables
        WHERE tenant = %s
          AND env = %s
          AND run_id = %s
          AND name = %s
        LIMIT 1
    """
    with (
        psycopg.connect(_psycopg_url(database_url), row_factory=dict_row) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, (tenant, env, run_id, table_name))
        row = cursor.fetchone()
    if row is None:
        return None
    return TableDictionary(
        table_name=row["name"],
        description_es=row.get("description_es"),
        description_en=row.get("description_en"),
        columns=_parse_columns(row.get("columns")),
    )


@lru_cache(maxsize=256)
def read_catalog_rows(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    table_name: str,
    limit: int,
    schema: str = _DEFAULT_SCHEMA,
) -> tuple[tuple[CatalogRow, ...], bool]:
    """Rows for one table, plus whether the cap hid more.

    ``limit`` is the configured tope; the query asks for ``limit + 1``. An
    empty result is "the table is not loaded for this run", not an empty
    catalog — the caller decides that.

    || Filas de una tabla, más si el tope escondió otras. Un resultado vacío
    es «la tabla no está cargada para esta corrida», no un catálogo vacío.
    """
    import psycopg
    from psycopg.rows import dict_row

    fetch = limit + 1
    sql = f"""
        SELECT row
        FROM {schema}.business_data
        WHERE tenant = %s
          AND env = %s
          AND run_id = %s
          AND table_name = %s
        LIMIT %s
    """
    with (
        psycopg.connect(_psycopg_url(database_url), row_factory=dict_row) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, (tenant, env, run_id, table_name, fetch))
        fetched = cursor.fetchall()
    capped = len(fetched) > limit
    kept = fetched[:limit]
    rows = tuple(CatalogRow(values=_row_values(item.get("row"))) for item in kept)
    return rows, capped


@lru_cache(maxsize=8)
def read_run_created_at(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    schema: str = _DEFAULT_SCHEMA,
) -> datetime | None:
    """The extractor's clock for this run — the default `as_of`. Never `now()`.

    || El reloj del extractor para esta corrida — el `as_of` por defecto.
    Nunca `now()`.
    """
    import psycopg
    from psycopg.rows import dict_row

    sql = f"""
        SELECT created_at_utc
        FROM {schema}.extraction_runs
        WHERE tenant = %s
          AND env = %s
          AND run_id = %s
        LIMIT 1
    """
    with (
        psycopg.connect(_psycopg_url(database_url), row_factory=dict_row) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, (tenant, env, run_id))
        row = cursor.fetchone()
    if row is None:
        return None
    return row.get("created_at_utc")


@lru_cache(maxsize=8)
def run_has_edges(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
) -> bool:
    """Whether the batch ever ran for this run.

    Asked of ``transaction_table_builds`` and NOT by counting edges: zero edges
    from a build that ran is a fact about the run, while zero edges because the
    batch never ran is a deployment gap. Collapsing them would let an
    administrator activate a run and silently get answers with no tables.

    || Si el batch alguna vez corrió para esta corrida. Se le pregunta a
    ``transaction_table_builds`` y NO contando aristas: cero aristas de un batch
    que corrió es un hecho; cero porque nunca corrió es un hueco de despliegue.
    """
    import psycopg

    sql = """
        SELECT 1
        FROM transaction_table_builds
        WHERE tenant = %s AND env = %s AND run_id = %s
        LIMIT 1
    """
    with (
        psycopg.connect(_psycopg_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, (tenant, env, run_id))
        return cursor.fetchone() is not None


@lru_cache(maxsize=512)
def read_dependency_tables(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    transaction_code: str,
    limit: int,
    schema: str = _DEFAULT_SCHEMA,
) -> tuple[tuple[DependencyTable, ...], int, tuple[str, ...]]:
    """The tables one code touches, highest coverage first, plus the real total.

    The total is the count BEFORE the cap, so a capped list can report what it
    is hiding instead of presenting itself as the whole set.

    || Las tablas que toca un código, mayor cobertura primero, más el total
    real. El total es el conteo ANTES del tope.
    """
    import psycopg
    from psycopg.rows import dict_row

    params = (tenant, env, run_id, transaction_code)
    with (
        psycopg.connect(_psycopg_url(database_url), row_factory=dict_row) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT count(*) AS n
            FROM transaction_table_edges
            WHERE tenant = %s AND env = %s AND run_id = %s AND transaction_code = %s
            """,
            params,
        )
        total = int((cursor.fetchone() or {}).get("n") or 0)
        # LEFT JOIN and not a second query per table: a name alone does not
        # inform -- CESSION_NPR and CESSION_PR are the whole answer to a
        # question about non-proportional reinsurance, and only the business
        # prose says which is which. LEFT so a table with no dictionary row
        # still comes back: the dependency is declared either way.
        # || LEFT JOIN y no una consulta por tabla. LEFT para que una tabla sin
        # ficha igual vuelva: la dependencia está declarada de todos modos.
        cursor.execute(
            f"""
            SELECT e.table_name, e.role, e.role_reason, e.via_routines,
                   e.routine_hits, e.routine_total, e.fan_in,
                   t.description_es, t.description_en
            FROM transaction_table_edges e
            LEFT JOIN {schema}.business_tables t
              ON t.tenant = e.tenant
             AND t.env = e.env
             AND t.run_id = e.run_id
             AND t.name = e.table_name
            WHERE e.tenant = %s AND e.env = %s AND e.run_id = %s
              AND e.transaction_code = %s
            ORDER BY e.routine_hits DESC, e.table_name ASC
            LIMIT %s
            """,
            (*params, max(limit, 0)),
        )
        rows = cursor.fetchall()
    routines: list[str] = []
    tables: list[DependencyTable] = []
    for row in rows:
        via = [name for name in (row.get("via_routines") or "").split(",") if name]
        for name in via:
            if name not in routines:
                routines.append(name)
        description = row.get("description_es") or row.get("description_en")
        tables.append(
            DependencyTable(
                table_name=row["table_name"],
                # First line only: the dictionary prose often runs several
                # lines and the block pays for every one of them.
                # || Solo la primera línea: la prosa suele tener varias y el
                # bloque las paga todas.
                description=description.splitlines()[0] if description else None,
                role=row["role"],
                role_reason=row["role_reason"],
                via_routines=via,
                routine_hits=int(row.get("routine_hits") or 0),
                routine_total=int(row.get("routine_total") or 0),
                fan_in=int(row.get("fan_in") or 0),
            )
        )
    return tuple(tables), total, tuple(sorted(routines))


@lru_cache(maxsize=128)
def read_table_dictionary_full(
    database_url: str,
    tenant: str,
    env: str,
    run_id: str,
    table_name: str,
    schema: str = _DEFAULT_SCHEMA,
) -> TableDictionaryDetail | None:
    """Everything the run declares about one table, or ``None`` when it has none.

    Oracle constraint types: ``P`` primary key, ``R`` referential, ``C`` check,
    ``U`` unique. Only ``P`` and ``R`` are keys, and the run has 1,881 of the
    first and 2,096 of the second -- the 12,232 ``C`` rows are check
    constraints and would be noise on a column list.

    || Todo lo que la corrida declara de una tabla. De los constraints solo
    ``P`` y ``R`` son claves; los ``C`` son checks y serían ruido.
    """
    import psycopg
    from psycopg.rows import dict_row

    sql = f"""
        SELECT name, description_es, description_en, columns, constraints, indexes
        FROM {schema}.business_tables
        WHERE tenant = %s AND env = %s AND run_id = %s AND name = %s
        LIMIT 1
    """
    with (
        psycopg.connect(_psycopg_url(database_url), row_factory=dict_row) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, (tenant, env, run_id, table_name))
        row = cursor.fetchone()
    if row is None:
        return None

    constraints = row.get("constraints") or []
    primary = [
        column
        for item in constraints
        if item.get("type") == "P"
        for column in (item.get("columns") or [])
    ]
    foreign = [
        DictionaryForeignKey(
            name=item.get("name") or "",
            columns=list(item.get("columns") or []),
            references_table=item.get("refTable"),
        )
        for item in constraints
        if item.get("type") == "R"
    ]
    in_foreign = {column for key in foreign for column in key.columns}

    raw_columns = row.get("columns")
    columns: list[DictionaryColumn] | None = None
    if raw_columns is not None:
        columns = [
            DictionaryColumn(
                name=str(item.get("name")),
                description=item.get("descriptionEs") or item.get("descriptionEn"),
                data_type=item.get("dataType"),
                nullable=item.get("nullable"),
                is_primary_key=str(item.get("name")) in set(primary),
                is_foreign_key=str(item.get("name")) in in_foreign,
            )
            for item in raw_columns
            if isinstance(item, dict) and item.get("name")
        ]

    indexes = [
        DictionaryIndex(
            name=item.get("name") or "",
            unique=bool(item.get("unique")),
            columns=[
                str(column.get("name"))
                for column in (item.get("columns") or [])
                if isinstance(column, dict) and column.get("name")
            ],
        )
        for item in (row.get("indexes") or [])
        if isinstance(item, dict)
    ]

    return TableDictionaryDetail(
        table_name=row["name"],
        description_es=row.get("description_es"),
        description_en=row.get("description_en"),
        columns=columns,
        primary_key=primary,
        foreign_keys=foreign,
        indexes=indexes,
        run_id=run_id,
        env=env,
    )


def clear_reader_cache() -> None:
    """Drop cached reads (tests). || Tira las lecturas cacheadas (tests)."""
    read_table_dictionary.cache_clear()
    read_catalog_rows.cache_clear()
    read_run_created_at.cache_clear()
    read_dependency_tables.cache_clear()
    read_table_dictionary_full.cache_clear()
    run_has_edges.cache_clear()
