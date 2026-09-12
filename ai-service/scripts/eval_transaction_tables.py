"""Measure whether the block puts the analyst's tables where they can be read.

The plan meant to measure precision of a `core` role. That role does not exist:
measured against this very set, no declared signal isolates it and the proposed
low-fan-in rule runs backwards (see `business_db/roles.py`). So what is measured
is what the block actually promises:

* **recall@N** -- does the annotated table survive the cap the block applies?
  This is the one that decides the flag: a table trimmed away is a table the
  answer cannot cite.
* **rank** -- where the coverage order puts it. Coverage is two declared counts,
  so a bad rank is a fact about the graph, not a mis-tuned weight.
* **role distribution** -- how much of the block says `unknown`. Expected to be
  high; it is reported so it stays a known quantity rather than a surprise.

Usage:
    uv run python scripts/eval_transaction_tables.py
    uv run python scripts/eval_transaction_tables.py --top 12

|| Mide si el bloque deja las tablas del analista donde se pueden leer. El plan
iba a medir precisión de un rol `core` que no existe: contra este mismo set,
ninguna señal declarada lo aísla. Se mide lo que el bloque promete.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden_transaction_tables.json"
REPORT = Path(__file__).resolve().parent.parent / "evals" / "TRANSACTION_TABLES_EVAL.md"

# Below this many annotated cases the numbers do not measure an ordering. The
# change says 20; refusing to bless the flag under that is the point of the
# gate, so the threshold lives here and not in a comment.
# || Debajo de esta cantidad de casos los números no miden un orden.
MIN_CASES_TO_BLESS = 20


def _read_edges(url: str, tenant: str, env: str, run_id: str, code: str, top: int):
    import psycopg
    from psycopg.rows import dict_row

    sql = """
        SELECT table_name, role, routine_hits, routine_total, fan_in
        FROM transaction_table_edges
        WHERE tenant = %s AND env = %s AND run_id = %s AND transaction_code = %s
        ORDER BY routine_hits DESC, table_name ASC
    """
    with (
        psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"), row_factory=dict_row) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, (tenant, env, run_id, code))
        rows = cursor.fetchall()
    return rows, rows[:top]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=0, help="Cap. Default: settings.")
    parser.add_argument("--run-id", default="", help="Mirror run. Default: the golden set's.")
    args = parser.parse_args()

    settings = get_settings()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cases = golden["cases"]
    run_id = args.run_id or golden["run_id"] or settings.BUSINESS_DB_RUN_ID
    top = args.top or settings.BUSINESS_DB_DEPENDENCY_MAX_TABLES
    tenant, env, url = settings.TENANT_ID, settings.BUSINESS_DB_ENV, settings.DATABASE_URL

    lines = [
        "# Tablas por transaccion - evaluacion",
        "",
        f"Corrida `{run_id}` - tope `{top}` - {len(cases)} casos anotados.",
        "",
        "| codigo | anotadas | en el tope | recall@N | posiciones | tablas totales |",
        "|---|---:|---:|---:|---|---:|",
    ]
    total_expected = 0
    total_found = 0
    roles: collections.Counter[str] = collections.Counter()
    worst_rank = 0
    for case in cases:
        code, expected = case["code"], case["tables"]
        rows, capped = _read_edges(url, tenant, env, run_id, code, top)
        if not rows:
            lines.append(f"| `{code}` | {len(expected)} | - | - | sin aristas | 0 |")
            total_expected += len(expected)
            continue
        order = {row["table_name"]: index + 1 for index, row in enumerate(rows)}
        kept = {row["table_name"] for row in capped}
        for row in capped:
            roles[row["role"]] += 1
        found = [name for name in expected if name in kept]
        ranks = [f"{name}#{order.get(name, '-')}" for name in expected]
        worst_rank = max(worst_rank, *(order.get(name, 0) for name in expected))
        total_expected += len(expected)
        total_found += len(found)
        recall = len(found) / len(expected) if expected else 1.0
        lines.append(
            f"| `{code}` | {len(expected)} | {len(found)} | {recall:.0%} | "
            f"{', '.join(ranks)} | {len(rows)} |"
        )

    overall = total_found / total_expected if total_expected else 0.0
    blessed = len(cases) >= MIN_CASES_TO_BLESS and overall >= 0.9
    lines.extend(
        [
            "",
            f"**recall@{top} global: {overall:.0%}** ({total_found}/{total_expected}).",
            f"Peor posicion de una tabla anotada: {worst_rank}.",
            "",
            "## Roles emitidos dentro del tope",
            "",
            "| rol | tablas |",
            "|---|---:|",
        ]
    )
    for role, count in roles.most_common():
        lines.append(f"| `{role}` | {count} |")
    lines.extend(
        [
            "",
            "## Veredicto",
            "",
            (
                f"**Habilitar `BUSINESS_DB_DEPENDENCY_TABLES_ENABLED`: "
                f"{'si' if blessed else 'NO'}.**"
            ),
            (
                f"Hacen falta {MIN_CASES_TO_BLESS} casos anotados y recall >= 90%; "
                f"hay {len(cases)} casos y recall {overall:.0%}."
            ),
            "",
            "No hay una columna de precision de `core` porque no hay rol `core`:",
            "ninguna senal declarada lo aisla y el fan-in bajo que proponia el plan",
            "corre al reves. Ver `app/generation/rag/business_db/roles.py`.",
            "",
        ]
    )
    report = "\n".join(lines)
    print(report)
    REPORT.write_text(report, encoding="utf-8")
    print(f"Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
