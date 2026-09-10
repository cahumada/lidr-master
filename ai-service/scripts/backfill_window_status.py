"""Backfill `window_status` on existing chunks from the WINDOWS mirror.

Updates metadata only — never `content_hash`, `embedding` or `token_count`.

Usage:
    uv run python scripts/backfill_window_status.py --dry-run
    uv run python scripts/backfill_window_status.py \\
        --tenant life_seguros \\
        --doc-version "DW Funtionals 2026.1" \\
        --run-id 20260909_214921

|| Backfill de `window_status` en chunks existentes desde el mirror WINDOWS.

Actualiza solo metadata — nunca `content_hash`, `embedding` ni `token_count`.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.navigation import WINDOW_STATUSES, load_navigation_tree_from_database_url

IMMUTABLE_COLUMNS = frozenset({"content_hash", "embedding", "token_count"})


def _status_by_document(tree, document_ids: set[str]) -> dict[str, str | None]:
    return {document_id: tree.window_status(document_id) for document_id in document_ids}


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
    run_id = args.run_id or settings.BUSINESS_DB_RUN_ID
    env = args.env or settings.BUSINESS_DB_ENV
    if not run_id:
        print(
            "run-id is required (flag or BUSINESS_DB_RUN_ID). "
            "|| run-id es obligatorio (flag o BUSINESS_DB_RUN_ID).",
            file=sys.stderr,
        )
        return 1

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
    print(f"rows {'would update' if args.dry_run else 'updated'}: {sum(chunks_by_document.values())}")
    assert IMMUTABLE_COLUMNS.isdisjoint({"window_status"}), "backfill must not touch identity columns"
    return 0


if __name__ == "__main__":
    sys.exit(main())
