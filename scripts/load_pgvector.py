"""Load the chunked corpus and its vectors into Postgres.

Reads ``data/chunks/<module>.json`` and ``data/embeddings/<module>.npy``, joins
them by ``content_hash``, and COPYs the result in. Idempotent: a row's identity
is ``(tenant_id, doc_version, content_hash)``, so re-running never grows the row
count. It DOES refresh the metadata columns of the rows it sees, which is what
lets a metadata-only change -- a new field, a corrected breadcrumb -- reach rows
that already exist.

Usage:
    docker compose up -d
    uv run alembic upgrade head
    uv run python scripts/load_pgvector.py --dry-run
    uv run python scripts/load_pgvector.py

|| Carga el corpus troceado y sus vectores en Postgres.

Lee ``data/chunks/<modulo>.json`` y ``data/embeddings/<modulo>.npy``, los une por
``content_hash`` y hace COPY del resultado. Idempotente: la identidad de una fila
es ``(tenant_id, doc_version, content_hash)``, así que volver a correr nunca hace
crecer el conteo de filas. SÍ refresca las columnas de metadata de las filas que
ve, que es lo que permite que un cambio solo de metadata —un campo nuevo, un
breadcrumb corregido— llegue a filas que ya existen.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.store.loader import iter_rows, load_module, prune_corpus

REPORT_FILENAME = "load_report.md"


def module_files(chunks_dir: Path) -> list[Path]:
    return sorted(p for p in chunks_dir.glob("*.json") if p.name != "manifest.json")


def corpus_identity(chunks_dir: Path) -> tuple[str, str, str]:
    path = chunks_dir / "manifest.json"
    if not path.exists():
        return "unknown", "unknown", "unknown"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return (
        manifest.get("corpus_id", "unknown"),
        manifest.get("tenant_id", "unknown"),
        manifest.get("doc_version", "unknown"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=Path("data/chunks"))
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--module", action="append", default=None)
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete rows of this corpus whose text is no longer in it. "
        "Only valid on a full run: pruning from a partial corpus deletes real rows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be loaded, connecting to nothing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    embeddings_root = args.embeddings or settings.EMBEDDINGS_PATH

    paths = module_files(args.chunks)
    if args.module:
        wanted = set(args.module)
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        print(f"No module JSON found under {args.chunks}", file=sys.stderr)
        return 1

    if args.prune and args.module:
        print(
            "--prune needs the whole corpus: with --module it would delete the "
            "rows of every module not loaded.",
            file=sys.stderr,
        )
        return 1

    corpus_id, tenant_id, doc_version = corpus_identity(args.chunks)

    # Read and join everything first, so --dry-run is a real preview and so a
    # missing sidecar is reported before any connection is opened.
    # || Se lee y se une todo primero, así --dry-run es una vista previa real y
    # un sidecar faltante se reporta antes de abrir ninguna conexión.
    prepared = []
    total_rows = 0
    total_without_vector = 0
    corpus_hashes: set[str] = set()
    for path in paths:
        module, rows, without_vector = iter_rows(path, embeddings_root)
        prepared.append((module, rows, without_vector))
        total_rows += len(rows)
        total_without_vector += len(without_vector)
        corpus_hashes.update(row[2] for row in rows)

    print(f"Corpus:             {corpus_id}")
    print(f"Tenant / version:   {tenant_id} / {doc_version}")
    print(f"Modules:            {len(prepared)}")
    print(f"Rows ready:         {total_rows:,}")
    print(f"Distinct texts:     {len(corpus_hashes):,}  (a repeated text is one row)")
    print(f"Chunks w/o vector:  {total_without_vector:,}")

    if args.dry_run:
        if total_without_vector:
            for module, _, without in prepared:
                if without:
                    print(f"  {module}: {len(without)} without a vector, e.g. {without[0]}")
        print("\n--dry-run: nothing was connected to and nothing was written.")
        return 0

    # Imported here so --dry-run never needs a reachable database.
    # || Se importa acá para que --dry-run nunca necesite una base alcanzable.
    from app.foundation.persistence.database import get_engine

    engine = get_engine()
    started = time.perf_counter()
    results = []

    with engine.raw_connection().driver_connection as connection:
        for module, rows, without_vector in prepared:
            copied, written = load_module(
                connection, rows, dimensions=settings.EMBEDDING_DIMENSIONS
            )
            connection.commit()
            results.append((module, copied, written, len(without_vector)))
            # "written" and not "inserted": the load upserts the metadata
            # columns, so a row that already existed is refreshed and counted.
            # || "escritas" y no "insertadas": la carga hace upsert de las
            # columnas de metadata, asi que una fila que ya existia se refresca y
            # se cuenta.
            print(
                f"  {module:<24} {written:>7,} written"
                + (f"  ({len(without_vector)} w/o vector)" if without_vector else "")
            )

        pruned = 0
        if args.prune:
            pruned = prune_corpus(connection, tenant_id, doc_version, corpus_hashes)
            connection.commit()
            print(f"  pruned: {pruned:,} rows whose text is no longer in the corpus")

    elapsed = time.perf_counter() - started
    # "written" and not "inserted": the load upserts metadata, so this counts
    # inserts AND updates. It can also EXCEED the table's row count, because the
    # staging table is per module and the 30 hashes that appear in two modules
    # get written twice. 57131 written against 57101 rows is exactly that.
    # || "escritas" y no "insertadas": la carga hace upsert de la metadata, asi
    # que esto cuenta inserts Y updates. Tambien puede SUPERAR el conteo de
    # filas, porque la staging es por modulo y los 30 hashes que estan en dos
    # modulos se escriben dos veces. 57131 escritas contra 57101 filas es eso.
    written_total = sum(r[2] for r in results)
    print(f"\n{written_total:,} rows written in {elapsed:.1f}s")

    report = render_report(corpus_id, tenant_id, doc_version, results, elapsed)
    (args.chunks / REPORT_FILENAME).write_text(report, encoding="utf-8")
    return 0


def render_report(corpus_id, tenant_id, doc_version, results, elapsed) -> str:
    lines = [
        "# Reporte de carga en pgvector",
        "",
        f"- Corpus: `{corpus_id}`",
        f"- Cliente / versión: `{tenant_id}` / `{doc_version}`",
        f"- Duración: {elapsed:.1f}s",
        "",
        "| Módulo | Preparadas | Escritas | Sin vector |",
        "|---|---:|---:|---:|",
    ]
    for module, copied, written, without in sorted(results, key=lambda r: -r[2]):
        lines.append(f"| {module} | {copied:,} | {written:,} | {without} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
