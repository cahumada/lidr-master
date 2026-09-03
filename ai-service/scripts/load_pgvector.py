"""Load the chunked corpus and its vectors into Postgres.

Reads ``data/chunks/<module>.json`` and ``data/embeddings/<module>.npy``, joins
them by ``content_hash``, and COPYs the result in. Idempotent: a row's identity
is ``(tenant_id, doc_version, source_type, content_hash)``, so re-running never grows the row
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
es ``(tenant_id, doc_version, source_type, content_hash)``, así que volver a correr nunca hace
crecer el conteo de filas. SÍ refresca las columnas de metadata de las filas que
ve, que es lo que permite que un cambio solo de metadata —un campo nuevo, un
breadcrumb corregido— llegue a filas que ya existen.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.pipeline import LoadStepResult, load_corpus

REPORT_FILENAME = "load_report.md"


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

    def progress(step: str, **fields) -> None:
        if "module" in fields:
            line = f"  {fields['module']:<24} {fields['written']:>7,} written"
            if fields["without_vector"]:
                line += f"  ({fields['without_vector']} w/o vector)"
            print(line)
        elif fields.get("phase") == "pruned":
            print(f"  pruned: {fields['pruned']:,} rows whose text is no longer in the corpus")

    # A library raises; a CLI turns that into an exit code. The pipeline is the
    # library, so the translation belongs here -- and a traceback is a worse
    # answer than one line and a 1.
    # || Una libreria lanza; una CLI lo convierte en un codigo de salida. El
    # pipeline es la libreria, asi que la traduccion va aca — y un traceback es
    # una respuesta peor que un renglon y un 1.
    try:
        started = time.perf_counter()
        result = load_corpus(
            chunks_dir=args.chunks,
            embeddings_dir=args.embeddings,
            modules=args.module,
            prune=args.prune,
            dry_run=args.dry_run,
            progress=progress,
        )
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - started

    print(f"Corpus:             {result.corpus_id}")
    print(f"Tenant / version:   {result.tenant_id} / {result.doc_version}")
    print(f"Modules:            {result.modules}")
    print(f"Rows ready:         {result.rows_ready:,}")
    print(f"Distinct texts:     {result.distinct_texts:,}  (a repeated text is one row)")
    print(f"Chunks w/o vector:  {result.chunks_without_vector:,}")

    if args.dry_run:
        print("\n--dry-run: nothing was connected to and nothing was written.")
        return 0

    # "written" and not "inserted": the load upserts metadata, so this counts
    # inserts AND updates. It can also EXCEED the table's row count, because the
    # staging table is per module and the 30 hashes that appear in two modules
    # get written twice. 57131 written against 57101 rows is exactly that.
    # || "escritas" y no "insertadas": la carga hace upsert de la metadata, asi
    # que esto cuenta inserts Y updates. Tambien puede SUPERAR el conteo de
    # filas, porque la staging es por modulo y los 30 hashes que estan en dos
    # modulos se escriben dos veces.
    print(f"\n{result.rows_written:,} rows written in {elapsed:.1f}s")

    (result.chunks_dir / REPORT_FILENAME).write_text(render_report(result, elapsed), encoding="utf-8")
    return 0


def render_report(result: LoadStepResult, elapsed: float) -> str:
    lines = [
        "# Reporte de carga en pgvector",
        "",
        f"- Corpus: `{result.corpus_id}`",
        f"- Cliente / versión: `{result.tenant_id}` / `{result.doc_version}`",
        f"- Duración: {elapsed:.1f}s",
        f"- Filas escritas: {result.rows_written:,}",
        f"- Podadas: {result.pruned:,}",
        "",
        "| Módulo | Preparadas | Escritas | Sin vector |",
        "|---|---:|---:|---:|",
    ]
    for module in sorted(result.per_module, key=lambda m: -m["written"]):
        lines.append(
            f"| {module['module']} | {module['copied']:,} | {module['written']:,} "
            f"| {module['without_vector']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
