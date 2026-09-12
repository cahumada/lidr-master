"""Build the tables each transaction touches, from Oracle's dependency graph.

Reads the corpus' `document_id`s and one extraction run of the mirror, does the
two hops, classifies each table, and loads the edges so the answer path can read
them by code.

It is a batch and not a per-request read for a reason that is about correctness,
not cost: the first hop matches a code inside a routine name, 184 codes are
substrings of another code, and disambiguating needs the whole universe of
codes. In a request only the hit codes are present, so `CA013` would arrive
without `CA013A` in sight and walk off with `INSPOSTCA013A` -- the same input
giving a different answer depending on which other hits came along.

Usage:
    uv run python scripts/build_transaction_tables.py --dry-run
    uv run python scripts/build_transaction_tables.py
    uv run python scripts/build_transaction_tables.py --run-id 20260909_214921

|| Arma las tablas que toca cada transacción desde el grafo de dependencias de
Oracle. Es un batch y no una lectura por request por corrección, no por costo:
desambiguar el salto por nombre necesita el universo entero de códigos.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.business_db.dependencies import (
    DEPENDENCY_GRAPH,
    build_edges,
    fan_in_by_table,
    routines_for_codes,
)

REPORT_FILENAME = "transaction_tables_report.md"

_INSERT_EDGE = """
INSERT INTO transaction_table_edges
    (tenant, env, run_id, transaction_code, table_name, role, role_reason,
     via_routines, fan_in, routine_hits, routine_total, origin)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (tenant, env, run_id, transaction_code, table_name) DO NOTHING
"""

_UPSERT_BUILD = """
INSERT INTO transaction_table_builds
    (tenant, env, run_id, edge_count, code_count, doc_version)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (tenant, env, run_id) DO UPDATE SET
    edge_count = EXCLUDED.edge_count,
    code_count = EXCLUDED.code_count,
    doc_version = EXCLUDED.doc_version,
    built_at = now()
"""


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://")


def _read_inputs(url: str, tenant: str, env: str, run_id: str, doc_version: str, schema: str):
    """Corpus codes, the run's routine->table edges, and the dictionary prose.

    || Códigos del corpus, aristas rutina->tabla de la corrida, y la prosa del
    diccionario.
    """
    import psycopg

    with psycopg.connect(_psycopg_url(url)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT document_id FROM chunks WHERE tenant_id = %s AND doc_version = %s",
            (tenant, doc_version),
        )
        codes = [row[0] for row in cursor.fetchall() if row[0]]

        cursor.execute(
            f"""
            SELECT source_name, target_name
            FROM {schema}.business_dependencies
            WHERE tenant = %s AND env = %s AND run_id = %s AND target_type = 'TABLE'
            """,
            (tenant, env, run_id),
        )
        pairs = [(row[0], row[1]) for row in cursor.fetchall()]

        cursor.execute(
            f"""
            SELECT name, description_es, description_en
            FROM {schema}.business_tables
            WHERE tenant = %s AND env = %s AND run_id = %s
            """,
            (tenant, env, run_id),
        )
        descriptions = {row[0]: (row[1] or row[2]) for row in cursor.fetchall()}
    return codes, pairs, descriptions


def _write(url: str, tenant: str, env: str, run_id: str, doc_version: str, built: dict) -> int:
    import psycopg

    # One executemany, not 5,907 round trips. The mirror lives on a managed
    # host and per-statement latency dominates: the same insert one row at a
    # time did not finish in 25 minutes.
    # || Un solo executemany y no 5.907 viajes. La latencia por sentencia manda.
    rows = [
        (
            tenant,
            env,
            run_id,
            code,
            edge.table_name,
            edge.role,
            edge.role_reason,
            ",".join(edge.via_routines),
            edge.fan_in,
            edge.routine_hits,
            edge.routine_total,
            DEPENDENCY_GRAPH,
        )
        for code, edges in built.items()
        for edge in edges
    ]
    with psycopg.connect(_psycopg_url(url)) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(_INSERT_EDGE, rows)
            written = len(rows)
            cursor.execute(
                _UPSERT_BUILD,
                (
                    tenant,
                    env,
                    run_id,
                    sum(len(edges) for edges in built.values()),
                    sum(1 for edges in built.values() if edges),
                    doc_version,
                ),
            )
        connection.commit()
    return written


def _report(run_id: str, doc_version: str, codes, code_routines, built, ambiguous) -> str:
    with_routines = sum(1 for names in code_routines.values() if names)
    with_tables = sum(1 for edges in built.values() if edges)
    pairs = sum(len(names) for names in code_routines.values())
    roles: collections.Counter[str] = collections.Counter()
    for edges in built.values():
        for edge in edges:
            roles[edge.role] += 1
    sizes = sorted(len(edges) for edges in built.values() if edges)
    median = sizes[len(sizes) // 2] if sizes else 0
    lines = [
        "# Tablas por transaccion - reporte de construccion",
        "",
        f"Corrida del mirror: `{run_id}` - corpus: `{doc_version}`",
        "",
        "| | |",
        "|---|---:|",
        f"| documentos del corpus | {len(codes)} |",
        f"| documentos que resuelven 1+ rutina | {with_routines} |",
        f"| pares codigo-rutina | {pairs} |",
        f"| documentos que llegan a 1+ tabla | {with_tables} |",
        f"| aristas codigo-tabla | {sum(len(e) for e in built.values())} |",
        f"| tablas por documento (mediana) | {median} |",
        f"| rutinas cedidas por munch maximo | {ambiguous} |",
        "",
        "## Aristas por rol",
        "",
        "| rol | aristas |",
        "|---|---:|",
    ]
    for role, count in roles.most_common():
        lines.append(f"| `{role}` | {count} |")
    lines.extend(
        [
            "",
            "`unknown` no es un defecto del batch: es lo que ninguna regla declarada",
            "clasificó. Ver `app/generation/rag/business_db/roles.py` para por qué no",
            "hay un rol `core`.",
            "",
        ]
    )
    return "\n".join(lines)


def _count_ambiguous(codes, routine_names) -> int:
    """Routines a shorter code would have taken without the longest-match rule.

    || Rutinas que un código más corto se habría llevado sin el munch máximo.
    """
    anchorable = sorted({c.strip().upper() for c in codes if len(c.strip()) >= 5})
    ceded = 0
    for name in routine_names:
        upper = name.upper()
        matches = [code for code in anchorable if code in upper]
        if len(matches) > 1:
            ceded += len(matches) - 1
    return ceded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="", help="Mirror run. Default: settings.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write.")
    parser.add_argument("--out", default="", help="Where to write the report.")
    args = parser.parse_args()

    settings = get_settings()
    run_id = args.run_id or settings.BUSINESS_DB_RUN_ID
    if not run_id:
        print("No run id: pass --run-id or set BUSINESS_DB_RUN_ID.", file=sys.stderr)
        return 1

    tenant = settings.TENANT_ID
    env = settings.BUSINESS_DB_ENV
    doc_version = settings.DOC_VERSION
    url = settings.DATABASE_URL

    codes, pairs, descriptions = _read_inputs(
        url, tenant, env, run_id, doc_version, "visualtime"
    )
    if not codes:
        print(f"No chunks for {tenant}/{doc_version}: nothing to anchor.", file=sys.stderr)
        return 1
    if not pairs:
        print(f"Run {run_id} has no table dependencies.", file=sys.stderr)
        return 1

    routine_tables: dict[str, list[str]] = collections.defaultdict(list)
    for routine, table in pairs:
        if table not in routine_tables[routine]:
            routine_tables[routine].append(table)

    code_routines = routines_for_codes(codes, routine_tables.keys())
    fan_in = fan_in_by_table(pairs)
    built = build_edges(
        code_routines=code_routines,
        routine_tables=routine_tables,
        descriptions=descriptions,
        fan_in=fan_in,
    )
    ambiguous = _count_ambiguous(codes, routine_tables.keys())
    report = _report(run_id, doc_version, codes, code_routines, built, ambiguous)
    print(report)

    if args.dry_run:
        print("--dry-run: nothing written.")
        return 0

    written = _write(url, tenant, env, run_id, doc_version, built)
    print(f"Sent {written} edge(s); build recorded for {run_id}.")
    target = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "evals" / REPORT_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    print(f"Report: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
