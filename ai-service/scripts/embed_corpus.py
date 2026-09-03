"""Embed the whole chunked corpus into binary vector sidecars.

Reads ``data/chunks/<module>.json`` (the output of ``chunk_corpus.py``) and
writes ``data/embeddings/<module>.npy`` plus ``<module>.index.json``, along with
a manifest and a markdown report.

The run is incremental and resumable: a row is identified by its
``content_hash``, so re-running over an unchanged corpus makes no API calls at
all, and an interrupted run picks up where it stopped. A batch that exhausts its
retries is reported and the run continues -- the exit code is non-zero so a
caller still knows something is missing.

Usage:
    uv run python scripts/embed_corpus.py --dry-run
    uv run python scripts/embed_corpus.py

|| Embebe todo el corpus troceado en sidecars binarios de vectores.

Lee ``data/chunks/<modulo>.json`` (la salida de ``chunk_corpus.py``) y escribe
``data/embeddings/<modulo>.npy`` más ``<modulo>.index.json``, junto con un
manifiesto y un reporte markdown.

La corrida es incremental y reanudable: una fila se identifica por su
``content_hash``, así que volver a correr sobre un corpus sin cambios no hace
ninguna llamada a la API, y una corrida interrumpida retoma donde quedó. Un lote
que agota sus reintentos se reporta y la corrida sigue — el código de salida es
distinto de cero para que quien la invoque igual sepa que falta algo.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.embedding.runner import ModuleResult, estimated_cost_usd
from app.generation.rag.schemas import EmbeddingManifest
from app.ingestion.pipeline import embed_corpus

# Console output stays ASCII: the Windows console this runs on is cp1252 and
# a single non-ASCII arrow aborted an already-finished run at its last line.
# The report file is UTF-8 and carries the accents.
# || La salida de consola se mantiene ASCII: la consola de Windows donde esto
# corre es cp1252 y una sola flecha no-ASCII abortó una corrida ya terminada
# en su último renglón. El archivo de reporte es UTF-8 y lleva los acentos.
REPORT_FILENAME = "embedding_report.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chunks", type=Path, default=Path("data/chunks"), help="Corpus directory."
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="Sidecar directory (default: EMBEDDINGS_PATH)."
    )
    parser.add_argument(
        "--module", action="append", default=None, help="Limit to these modules (repeatable)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be embedded and what it would cost, calling nothing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    out_dir = args.out or settings.EMBEDDINGS_PATH

    def progress(step: str, **fields) -> None:
        if fields.get("phase") == "planned":
            return
        if "module" in fields:
            print(
                f"  {fields['module']:<24} +{fields['embedded']:>6,} new"
                f"  ({fields['done']}/{fields['total']})"
            )

    # A library raises; a CLI turns that into an exit code. The pipeline is the
    # library, so the translation belongs here -- and a traceback is a worse
    # answer than one line and a 1.
    # || Una libreria lanza; una CLI lo convierte en un codigo de salida. El
    # pipeline es la libreria, asi que la traduccion va aca — y un traceback es
    # una respuesta peor que un renglon y un 1.
    try:
        started = time.perf_counter()
        result = embed_corpus(
            chunks_dir=args.chunks,
            out_dir=out_dir,
            modules=args.module,
            dry_run=args.dry_run,
            progress=progress,
        )
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - started

    print(f"Modules:            {result.modules}")
    print(f"Rows to embed:      {result.to_embed:,}")
    print(f"Rows reused:        {result.reused:,}")
    print(f"Duplicates saved:   {result.duplicates_saved:,}")
    print(f"Tokens to bill:     {result.tokens_billed:,}")
    print(f"Batches:            {result.batches:,} (size {settings.EMBEDDING_BATCH_SIZE})")
    print(f"Estimated cost:     US$ {result.estimated_cost_usd:.4f}")

    if args.dry_run:
        print("\n--dry-run: nothing was called and nothing was written.")
        return 0
    if result.to_embed == 0:
        print("\nNothing to embed - every content_hash already has a vector.")
        return 0

    # The manifest is written by the pipeline, because the rebuild endpoint runs
    # the same step and a run that embeds without leaving its record cannot be
    # audited. Only the human-readable report is built here.
    # || El manifiesto lo escribe el pipeline, porque el endpoint de rebuild
    # corre el mismo paso y una corrida que embebe sin dejar registro no se puede
    # auditar. Aca solo se arma el reporte legible.
    (result.out_dir / REPORT_FILENAME).write_text(
        render_report(result.manifest, result.module_results, elapsed), "utf-8"
    )

    print(f"\n{result.rows_written:,} rows in {elapsed:.1f}s -> {out_dir}")
    if result.failed_batches:
        print(
            f"{result.failed_batches} batch(es) failed and were NOT embedded. "
            f"Re-run to retry only those. See {result.out_dir / REPORT_FILENAME}",
            file=sys.stderr,
        )
        return 1
    return 0


def render_report(
    manifest: EmbeddingManifest, results: list[ModuleResult], elapsed: float
) -> str:
    lines = [
        "# Reporte de embeddings",
        "",
        f"- Corpus: `{manifest.corpus_id}`",
        f"- Cliente / versión: `{manifest.tenant_id}` / `{manifest.doc_version}`",
        f"- Modelo: `{manifest.model}` ({manifest.dimensions} dims)",
        f"- Generado: {manifest.generated_at}",
        f"- Duración: {elapsed:.1f}s",
        "",
        "## Totales",
        "",
        f"- Filas persistidas: **{manifest.total_rows:,}**",
        f"- Embebidas en esta corrida: {manifest.embedded_now:,}",
        f"- Reutilizadas por `content_hash`: {manifest.reused:,}",
        f"- Descartadas (su chunk ya no existe): {manifest.dropped:,}",
        (
            f"- Tokens facturados: {manifest.tokens_billed:,} "
            f"(~US$ {estimated_cost_usd(manifest.tokens_billed):.4f})"
        ),
        "",
        "## Por módulo",
        "",
        "| Módulo | Filas | Nuevas | Reutilizadas | Duplicados ahorrados | Lotes fallidos |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for result in sorted(results, key=lambda r: -r.rows_written):
        lines.append(
            f"| {result.module} | {result.rows_written:,} | {result.embedded:,} | "
            f"{result.reused:,} | {result.duplicates_saved:,} | {len(result.failed)} |"
        )

    if manifest.failed_batches:
        lines += [
            "",
            "## Lotes fallidos",
            "",
            "Sus hashes quedaron fuera del sidecar: volver a correr el batch los",
            "reintenta y no vuelve a pagar nada de lo que ya está.",
            "",
        ]
        for batch in manifest.failed_batches:
            lines.append(f"- **{batch.module}** ({batch.size} chunks): {batch.error}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
