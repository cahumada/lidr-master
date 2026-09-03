"""Batch: trocea el corpus entero de especificaciones funcionales.

La orquestación vive en ``app.ingestion.pipeline`` y no acá: el endpoint
``POST /corpus/rebuild`` necesita la misma secuencia, y dos implementaciones de
lo mismo divergen. Este script es la cara de consola del pipeline — argumentos,
reporte y salida por pantalla.

Uso:
    uv run python scripts/chunk_corpus.py --root "D:\\EspecificacionesFuncionales_md"

|| Batch: chunks the whole functional-spec corpus.

The orchestration lives in ``app.ingestion.pipeline`` and not here: the
``POST /corpus/rebuild`` endpoint needs the same sequence, and two
implementations of the same thing drift apart. This script is the pipeline's
console face -- arguments, report and stdout.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
# || Run as a script (not `python -m`), so add the repo root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.pipeline import ChunkStepResult, chunk_corpus
from app.ingestion.source import LocalCorpusSource

REPORT_FILENAME = "chunking_report.md"


def render_report(result: ChunkStepResult, elapsed: float) -> str:
    """El reporte markdown, armado del resultado estructurado del pipeline.

    || The markdown report, built from the pipeline's structured result.
    """
    lines = [
        "# Reporte de chunking del corpus",
        "",
        f"Fuente: `{result.source}`",
        f"Módulos procesados: {result.modules}",
        f"Corpus: `{result.corpus_id}`",
        f"Tenant / versión: {result.tenant_id} / {result.doc_version}",
        "",
        (
            "| Módulo | Archivos | Documentos OK | Chunks | Tokens | Tabla | Narrativa "
            "| 0 chunks | Fallidos |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for module in result.per_module:
        lines.append(
            f"| {module['module']} | {module['files']} | {module['documents']} "
            f"| {module['chunks']} | {module['tokens']:,} | {module['table']} "
            f"| {module['narrative']} | {module['zero_chunks']} | {module['failed']} |"
        )
    lines += [
        (
            f"| **Total** | **{result.files}** | **{result.documents}** | **{result.chunks}** "
            f"| **{result.tokens:,}** | | | **{len(result.zero_chunk_files)}** "
            f"| **{len(result.failed_files)}** |"
        ),
        "",
        f"Tiempo: {elapsed:.1f}s",
    ]

    # Los dos modos de falla se listan enteros y nunca se resumen: un archivo que
    # produjo cero chunks es una regla de negocio que no entró al índice.
    # || Both failure modes are listed in full and never summarised: a file that
    # produced zero chunks is a business rule that never reached the index.
    if result.zero_chunk_files:
        lines += ["", "## Archivos con 0 chunks", ""]
        lines += [f"- `{f['file']}` ({f['document_id']})" for f in result.zero_chunk_files]
    if result.failed_files:
        lines += ["", "## Archivos fallidos", ""]
        lines += [f"- `{f['file']}` — {f['error']}" for f in result.failed_files]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", required=True, help="Corpus root, e.g. D:\\EspecificacionesFuncionales_md"
    )
    parser.add_argument("--out", default="data/chunks", help="Output directory (default: data/chunks)")
    parser.add_argument(
        "--modules", nargs="*", default=None, help="Only these modules (default: all found under --root)"
    )
    parser.add_argument("--tenant", default=None, help="Client id (default: TENANT_ID setting)")
    parser.add_argument(
        "--doc-version", default=None, help="Documentation set version (default: DOC_VERSION setting)"
    )
    args = parser.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out)

    def progress(step: str, **fields) -> None:
        if "module" in fields:
            print(
                f"  {fields['module']:<24} {fields['files']:>5} archivos"
                f" -> {fields['chunks']:>6} chunks"
                f"  ({fields['done']}/{fields['total']})"
            )

    started = time.perf_counter()
    result = chunk_corpus(
        source=LocalCorpusSource(root),
        out_dir=out_dir,
        modules=args.modules,
        tenant_id=args.tenant,
        doc_version=args.doc_version,
        progress=progress,
    )
    elapsed = time.perf_counter() - started

    (out_dir / REPORT_FILENAME).write_text(
        render_report(result, elapsed), encoding="utf-8"
    )

    print(
        f"\nTotal: {result.files} archivos -> {result.chunks} chunks, "
        f"{result.tokens} tokens en {elapsed:.1f}s"
    )
    print(f"0 chunks: {len(result.zero_chunk_files)} | fallidos: {len(result.failed_files)}")
    print(f"Reporte: {out_dir / REPORT_FILENAME}")
    print(f"Tenant/version: {result.tenant_id} / {result.doc_version}  (manifest.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
