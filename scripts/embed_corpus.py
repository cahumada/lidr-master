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
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.embedding.runner import (
    ModuleResult,
    embed_module,
    estimated_cost_usd,
    load_module_chunks,
    plan_module,
    verify_before_embedding,
    verify_module_on_disk,
)
from app.generation.rag.embedding.sidecar import load_sidecar
from app.generation.rag.schemas import EmbeddingManifest

# Console output stays ASCII: the Windows console this runs on is cp1252 and
# a single "→" aborted a completed run at the last line. The report file is
# UTF-8 and carries the accents.
# || La salida de consola se mantiene ASCII: la consola de Windows donde esto
# corre es cp1252 y un solo "→" abortó una corrida ya terminada en el último
# renglón. El archivo de reporte es UTF-8 y lleva los acentos.
# Console output stays ASCII: the Windows console this runs on is cp1252 and
# a single non-ASCII arrow aborted an already-finished run at its last line.
# The report file is UTF-8 and carries the accents.
# || La salida de consola se mantiene ASCII: la consola de Windows donde esto
# corre es cp1252 y una sola flecha no-ASCII abortó una corrida ya terminada
# en su último renglón. El archivo de reporte es UTF-8 y lleva los acentos.
MANIFEST_FILENAME = "embeddings_manifest.json"
REPORT_FILENAME = "embedding_report.md"


def module_files(chunks_dir: Path) -> list[Path]:
    """Every module JSON in the corpus directory, manifest excluded.

    || Cada JSON de módulo en el directorio del corpus, sin el manifiesto.
    """
    return sorted(p for p in chunks_dir.glob("*.json") if p.name != "manifest.json")


def corpus_identity(chunks_dir: Path) -> tuple[str, str, str]:
    """``(corpus_id, tenant_id, doc_version)`` from the corpus manifest.

    || ``(corpus_id, tenant_id, doc_version)`` del manifiesto del corpus.
    """
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

    paths = module_files(args.chunks)
    if args.module:
        wanted = set(args.module)
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        print(f"No module JSON found under {args.chunks}", file=sys.stderr)
        return 1

    corpus_id, tenant_id, doc_version = corpus_identity(args.chunks)

    # --- Plan everything first, so a --dry-run is a real preview -------------
    # || Se planifica todo primero, así un --dry-run es una vista previa real.
    plans = []
    for path in paths:
        module, chunks = load_module_chunks(path)
        verify_before_embedding(chunks, max_input_tokens=settings.EMBEDDING_MAX_INPUT_TOKENS)
        _, existing_index = load_sidecar(out_dir, module)
        plans.append((module, chunks, plan_module(module, chunks, existing_index)))

    to_embed = sum(len(plan.to_embed) for _, _, plan in plans)
    tokens = sum(plan.tokens_to_bill for _, _, plan in plans)
    batches = sum(plan.batches(settings.EMBEDDING_BATCH_SIZE) for _, _, plan in plans)
    reused = sum(plan.reused for _, _, plan in plans)
    duplicates = sum(plan.duplicates_saved for _, _, plan in plans)

    print(f"Modules:            {len(plans)}")
    print(f"Rows to embed:      {to_embed:,}")
    print(f"Rows reused:        {reused:,}")
    print(f"Duplicates saved:   {duplicates:,}")
    print(f"Tokens to bill:     {tokens:,}")
    print(f"Batches:            {batches:,} (size {settings.EMBEDDING_BATCH_SIZE})")
    print(f"Estimated cost:     US$ {estimated_cost_usd(tokens):.4f}")

    if args.dry_run:
        print("\n--dry-run: nothing was called and nothing was written.")
        return 0

    if to_embed == 0:
        print("\nNothing to embed - every content_hash already has a vector.")
        return 0

    # Imported here so --dry-run never needs an API key.
    # || Se importa acá para que --dry-run nunca necesite una clave de API.
    from app.dependencies import get_embedder

    embedder = get_embedder()
    started = time.perf_counter()
    results: list[ModuleResult] = []

    for module, chunks, plan in plans:
        existing_vectors, existing_index = load_sidecar(out_dir, module)
        result = embed_module(
            plan,
            embedder=embedder,
            root=out_dir,
            existing_vectors=existing_vectors,
            existing_index=existing_index,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            checkpoint_every=settings.EMBEDDING_CHECKPOINT_EVERY,
        )
        verify_module_on_disk(
            out_dir,
            module,
            dimensions=embedder.dimensions,
            corpus_hashes={chunk.content_hash for chunk in chunks},
        )
        results.append(result)
        print(
            f"  {module:<24} {result.rows_written:>7,} rows  "
            f"(+{result.embedded:,} new, {result.reused:,} reused)"
            + (f"  {len(result.failed)} FAILED BATCHES" if result.failed else "")
        )

    elapsed = time.perf_counter() - started
    failed = [batch for result in results for batch in result.failed]

    manifest = EmbeddingManifest(
        corpus_id=corpus_id,
        tenant_id=tenant_id,
        doc_version=doc_version,
        model=embedder.model,
        dimensions=embedder.dimensions,
        generated_at=datetime.now(UTC).isoformat(),
        total_rows=sum(result.rows_written for result in results),
        embedded_now=sum(result.embedded for result in results),
        reused=sum(result.reused for result in results),
        dropped=sum(result.dropped for result in results),
        tokens_billed=sum(result.tokens_billed for result in results),
        failed_batches=failed,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / MANIFEST_FILENAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / REPORT_FILENAME).write_text(render_report(manifest, results, elapsed), "utf-8")

    print(f"\n{manifest.total_rows:,} rows in {elapsed:.1f}s -> {out_dir}")
    if failed:
        print(
            f"{len(failed)} batch(es) failed and were NOT embedded. "
            f"Re-run to retry only those. See {out_dir / REPORT_FILENAME}",
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
