"""Backfill `window_status` on existing chunks from the WINDOWS mirror.

Updates metadata only — never `content_hash`, `embedding` or `token_count`.

Usage:
    uv run python scripts/backfill_window_status.py --dry-run
    uv run python scripts/backfill_window_status.py \\
        --tenant life_seguros \\
        --doc-version "DW Funtionals 2026.1" \\
        --run-id 20260909_214921

On success it records the stamp in `business_db_stamp`: which run, when, and
how many rows. That row is what makes the drift visible later — the console can
say "stamped with X · active Y" instead of nobody noticing that the column
belongs to a run that is no longer selected. Recording it is part of stamping,
not a nicety: a stamp whose provenance was not written down is a value with no
way to check it.

Defaults to the ACTIVE run and not to `BUSINESS_DB_RUN_ID`. Stamping the corpus
from the configured run while the service answers from a selected one would
create the exact drift this script's own bookkeeping exists to expose.

|| Backfill de `window_status` en chunks existentes desde el mirror WINDOWS.

Actualiza solo metadata — nunca `content_hash`, `embedding` ni `token_count`.

Al terminar registra el sello en `business_db_stamp`: con qué corrida, cuándo y
cuántas filas. Esa fila es lo que después hace visible el desfasaje. Y el default
es la corrida ACTIVA y no `BUSINESS_DB_RUN_ID`: estampar desde la configurada
mientras el servicio responde desde la seleccionada crearía justo el desfasaje
que esta contabilidad existe para mostrar.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.domain.business_db_store import resolve_active_run_sync
from app.generation.rag.navigation import WINDOW_STATUSES, load_navigation_tree_from_database_url

IMMUTABLE_COLUMNS = frozenset({"content_hash", "embedding", "token_count"})


def _status_by_document(tree, document_ids: set[str]) -> dict[str, str | None]:
    return {document_id: tree.window_status(document_id) for document_id in document_ids}


def _record_stamp(
    cursor, *, tenant: str, doc_version: str, env: str, run_id: str, rows_updated: int
) -> None:
    """Write the stamp with plain SQL, on the cursor already in hand.

    Plain SQL and not the async store: this script runs on psycopg and opening
    an async engine beside the connection that just did the update would put the
    stamp in a different transaction from the thing it describes.

    One row per ``(tenant, doc_version)``, so a re-stamp replaces the previous
    one — there is only ever one stamped state for a corpus version.

    || SQL directo y no el store async: este script corre sobre psycopg, y abrir
    un engine async al lado de la conexión que acaba de hacer el update pondría
    el sello en otra transacción que la cosa que describe. Una fila por
    ``(tenant, doc_version)``: re-estampar reemplaza, porque solo hay un estado
    estampado por versión.
    """
    cursor.execute(
        """
            INSERT INTO public.business_db_stamp
                (tenant_id, doc_version, env, run_id, stamped_at, rows_updated)
            VALUES (%s, %s, %s, %s, now(), %s)
            ON CONFLICT (tenant_id, doc_version) DO UPDATE
            SET env = EXCLUDED.env,
                run_id = EXCLUDED.run_id,
                stamped_at = EXCLUDED.stamped_at,
                rows_updated = EXCLUDED.rows_updated
            """,
        (tenant, doc_version, env, run_id, rows_updated),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None, help="Tenant id (default: Settings.TENANT_ID)")
    parser.add_argument(
        "--doc-version",
        default=None,
        help="Documentation version (default: Settings.DOC_VERSION)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Mirror run id (default: Settings.BUSINESS_DB_RUN_ID)",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Mirror env (default: Settings.BUSINESS_DB_ENV)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    tenant = args.tenant or settings.TENANT_ID
    doc_version = args.doc_version or settings.DOC_VERSION
    # The ACTIVE run, not the configured one. The flags still win, because a
    # deliberate re-stamp of a specific run is a real need — but the default has
    # to be what the service is answering with.
    # || La corrida ACTIVA, no la configurada. Los flags siguen ganando porque
    # re-estampar una corrida concreta es una necesidad real, pero el default
    # tiene que ser aquello con lo que el servicio está respondiendo.
    active = resolve_active_run_sync(settings.DATABASE_URL, settings, tenant)
    run_id = args.run_id or active.run_id
    env = args.env or active.env
    if not run_id:
        print(
            f"No hay corrida con la que estampar. {active.reason or ''} "
            "Pasá --run-id o activá una corrida. "
            "|| No run to stamp with: pass --run-id or activate one.",
            file=sys.stderr,
        )
        return 1
    print(f"corrida: {run_id!r} (origen: {active.origin if not args.run_id else 'flag'})")

    tree = load_navigation_tree_from_database_url(
        settings.DATABASE_URL,
        tenant=tenant,
        env=env,
        run_id=run_id,
    )

    import psycopg

    url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT DISTINCT document_id
                FROM public.chunks
                WHERE tenant_id = %s AND doc_version = %s
                """,
            (tenant, doc_version),
        )
        document_ids = {row[0] for row in cursor.fetchall()}

        status_by_document = _status_by_document(tree, document_ids)
        unmatched_documents = sorted(
            document_id
            for document_id, status in status_by_document.items()
            if status is None
        )

        cursor.execute(
            """
                SELECT document_id, count(1)
                FROM public.chunks
                WHERE tenant_id = %s AND doc_version = %s
                GROUP BY document_id
                """,
            (tenant, doc_version),
        )
        chunks_by_document = {row[0]: row[1] for row in cursor.fetchall()}

        updates: list[tuple[str | None, str, str, str]] = []
        status_chunk_counts: Counter[str | None] = Counter()
        for document_id, chunk_count in chunks_by_document.items():
            status = status_by_document.get(document_id)
            status_chunk_counts[status] += chunk_count
            updates.append((status, tenant, doc_version, document_id))

        rows_updated = sum(chunks_by_document.values())
        if not args.dry_run:
            cursor.executemany(
                """
                    UPDATE public.chunks
                    SET window_status = %s
                    WHERE tenant_id = %s
                      AND doc_version = %s
                      AND document_id = %s
                    """,
                updates,
            )
            # The stamp goes in the SAME transaction as the update. A commit in
            # between could leave the column stamped with no record of which run
            # did it, which is worse than not stamping: an unexplained value
            # cannot be checked, and the drift becomes invisible again.
            # || El sello va en la MISMA transacción que el update. Un commit en
            # el medio podría dejar la columna estampada sin registro de qué
            # corrida lo hizo, que es peor que no estampar: un valor sin
            # explicación no se puede comprobar.
            _record_stamp(
                cursor,
                tenant=tenant,
                doc_version=doc_version,
                env=env,
                run_id=run_id,
                rows_updated=rows_updated,
            )
            connection.commit()

    resolved_counts = {
        (status or "(sin resolver)"): count for status, count in status_chunk_counts.items()
    }
    print(f"tenant={tenant!r} doc_version={doc_version!r} run_id={run_id!r}")
    print(f"documents in corpus: {len(document_ids)}")
    print(f"documents without a matching window status: {len(unmatched_documents)}")
    print(f"status normalized from 4 at tree load: {tree.status_normalized_from_4}")
    print("chunks by resolved status:")
    for status_name in (*WINDOW_STATUSES.values(), "(sin resolver)"):
        if status_name in resolved_counts:
            print(f"  {status_name}: {resolved_counts[status_name]}")
    print(f"rows {'would update' if args.dry_run else 'updated'}: {rows_updated}")
    if args.dry_run:
        print("dry-run: no se escribió el sello en `business_db_stamp`.")
    else:
        print(f"sello registrado: run_id={run_id!r} env={env!r} rows={rows_updated}")
    assert IMMUTABLE_COLUMNS.isdisjoint({"window_status"}), "backfill must not touch identity columns"
    return 0


if __name__ == "__main__":
    sys.exit(main())
