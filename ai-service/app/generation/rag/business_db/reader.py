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
    TableDictionary,
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


def clear_reader_cache() -> None:
    """Drop cached reads (tests). || Tira las lecturas cacheadas (tests)."""
    read_table_dictionary.cache_clear()
    read_catalog_rows.cache_clear()
    read_run_created_at.cache_clear()
