"""Batch-run FunctionalSpecChunker over the whole functional-spec corpus.

Walks a root directory of the shape ``<root>/<module>/*.md`` (the real
corpus: ``policies``, ``life``, ``claims``, ``collections``, ... — 30
modules) and chunks every file, writing one JSON file per module under the
output directory plus a single markdown report. One bad file never aborts
the run: it's caught, logged, and counted as a failure in the report.

Usage:
    uv run python scripts/chunk_corpus.py --root "D:\\EspecificacionesFuncionales_md" --out data/chunks

|| Corre FunctionalSpecChunker en lote sobre todo el corpus de
especificaciones funcionales. Recorre un directorio raíz con la forma
``<root>/<modulo>/*.md`` (el corpus real: ``policies``, ``life``,
``claims``, ``collections``, ... — 30 módulos) y trocea cada archivo,
escribiendo un JSON por módulo bajo el directorio de salida más un reporte
markdown único. Un archivo con error nunca aborta la corrida: se captura,
se loguea, y se cuenta como falla en el reporte.

Uso:
    uv run python scripts/chunk_corpus.py --root "D:\\EspecificacionesFuncionales_md" --out data/chunks
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.dependencies import get_functional_spec_chunker
from app.generation.rag.chunking.functional_spec import FunctionalSpecChunker
from app.generation.rag.schemas import CorpusManifest

# Project documentation living at the corpus root, not functional-spec
# transaction documents — never chunk these as if they were.
# || Documentación del proyecto que vive en la raíz del corpus, no
# documentos de transacción de especificación funcional — nunca trocearlos
# como si lo fueran.
EXCLUDED_FILENAMES = {"processing_report.md", "prompt_procesamiento_rag.md"}


def discover_modules(root: Path) -> dict[str, list[Path]]:
    """Group every ``.md`` file under ``root`` by its top-level module directory.

    || Agrupa cada archivo ``.md`` bajo ``root`` por su directorio de módulo de primer nivel.
    """
    modules: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("*.md")):
        if path.parent == root and path.name in EXCLUDED_FILENAMES:
            continue
        module = path.relative_to(root).parts[0]
        modules.setdefault(module, []).append(path)
    return modules


def chunk_module(
    chunker: FunctionalSpecChunker, root: Path, module: str, paths: list[Path]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Chunk every file in one module.

    Returns (documents, zero_chunk_files, failed_files) — the last two are
    flagged separately in the report since they're the failure modes worth a
    human look (a parseable file that yielded nothing, vs. one that raised).

    || Trocea cada archivo de un módulo. Devuelve (documents,
    zero_chunk_files, failed_files) — las dos últimas se marcan aparte en el
    reporte porque son los modos de falla que ameritan una mirada humana
    (un archivo parseable que no produjo nada, vs. uno que lanzó una excepción).
    """
    documents: list[dict] = []
    zero_chunk_files: list[dict] = []
    failed_files: list[dict] = []

    for path in paths:
        relative = str(path.relative_to(root))
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            failed_files.append({"file": relative, "error": f"decode error: {exc}"})
            continue
        try:
            chunked = chunker.chunk(path.name, content)
        except Exception as exc:  # noqa: BLE001 — one bad file must not abort the batch.
            failed_files.append({"file": relative, "error": f"{type(exc).__name__}: {exc}"})
            continue

        if not any(doc.chunks for doc in chunked):
            ids = ", ".join(doc.document_id for doc in chunked)
            zero_chunk_files.append({"file": relative, "document_id": ids})

        # One source file can describe several transactions, so it contributes
        # one entry per transaction rather than one entry per file.
        # || Un archivo fuente puede describir varias transacciones, así que
        # aporta una entrada por transacción en vez de una por archivo.
        for doc in chunked:
            documents.append(
                {
                    "source_file": path.name,
                    "module": module,
                    "document_id": doc.document_id,
                    "document_title": doc.document_title,
                    "parent_transaction_code": doc.parent_transaction_code,
                    "is_container": doc.is_container,
                    "transaction_type": doc.transaction_type,
                    "transaction_type_reason": doc.transaction_type_reason,
                    "document_kind": doc.document_kind,
                    "child_links": doc.child_links,
                    "navigation_path": doc.navigation_path,
                    "is_menu_node": doc.is_menu_node,
                    "content_hash": doc.content_hash,
                    "source_revision": doc.source_revision,
                    "valid_from": doc.valid_from.isoformat() if doc.valid_from else None,
                    "chunks": [chunk.model_dump() for chunk in doc.chunks],
                }
            )

    return documents, zero_chunk_files, failed_files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Corpus root, e.g. D:\\EspecificacionesFuncionales_md")
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
    out_dir.mkdir(parents=True, exist_ok=True)

    modules = discover_modules(root)
    if args.modules:
        modules = {name: paths for name, paths in modules.items() if name in args.modules}

    # Built through the composition root, so the batch run and the HTTP API
    # share one configuration — including the WINDOWS navigation tree.
    # Constructing the chunker directly here silently left the breadcrumb
    # unresolved for the whole corpus.
    # || Se construye por la raíz de composición, así la corrida batch y la
    # API HTTP comparten una única configuración — incluido el árbol de
    # navegación de WINDOWS. Construir el chunker directo acá dejaba el
    # breadcrumb sin resolver en todo el corpus, en silencio.
    settings = get_settings()
    tenant_id = args.tenant or settings.TENANT_ID
    doc_version = args.doc_version or settings.DOC_VERSION
    if args.tenant or args.doc_version:
        # A per-run override cannot come from the cached DI singleton.
        # || Un override por corrida no puede venir del singleton cacheado de DI.
        from app.generation.rag.navigation import get_navigation_tree

        chunker = FunctionalSpecChunker(
            narrative_token_cap=settings.NARRATIVE_CHUNK_TOKEN_CAP,
            index_doc_min_links=settings.INDEX_DOC_MIN_LINKS,
            index_doc_min_link_density=settings.INDEX_DOC_MIN_LINK_DENSITY,
            navigation_tree=get_navigation_tree(settings.WINDOWS_TREE_PATH),
            tenant_id=tenant_id,
            doc_version=doc_version,
        )
    else:
        chunker = get_functional_spec_chunker()

    report_lines = [
        "# Reporte de chunking del corpus",
        "",
        f"Raíz: `{root}`",
        f"Módulos procesados: {len(modules)}",
        "",
        "| Módulo | Archivos | Documentos OK | Chunks | Tokens | Tabla | Narrativa | 0 chunks | Fallidos |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    total_files = 0
    total_documents = 0
    total_chunks = 0
    total_tokens = 0
    total_zero = 0
    total_failed = 0
    all_zero_chunk_files: list[dict] = []
    all_failed_files: list[dict] = []

    t0 = time.perf_counter()
    for module, paths in modules.items():
        documents, zero_chunk_files, failed_files = chunk_module(chunker, root, module, paths)

        module_chunks = sum(len(d["chunks"]) for d in documents)
        module_tokens = sum(c["token_count"] for d in documents for c in d["chunks"])
        module_table = sum(
            1 for d in documents for c in d["chunks"] if c["metadata"]["chunk_type"] == "table"
        )
        module_narrative = sum(
            1 for d in documents for c in d["chunks"] if c["metadata"]["chunk_type"] == "narrative"
        )

        out_path = out_dir / f"{module}.json"
        out_path.write_text(
            json.dumps({"module": module, "documents": documents}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        report_lines.append(
            f"| {module} | {len(paths)} | {len(documents)} | {module_chunks} | {module_tokens} | "
            f"{module_table} | {module_narrative} | {len(zero_chunk_files)} | {len(failed_files)} |"
        )

        total_files += len(paths)
        total_documents += len(documents)
        total_chunks += module_chunks
        total_tokens += module_tokens
        total_zero += len(zero_chunk_files)
        total_failed += len(failed_files)
        all_zero_chunk_files.extend(zero_chunk_files)
        all_failed_files.extend(failed_files)

        print(f"{module}: {len(paths)} files -> {module_chunks} chunks ({len(paths)} total so far)")

    elapsed = time.perf_counter() - t0

    report_lines.append(
        f"| **Total** | **{total_files}** | | **{total_chunks}** | **{total_tokens}** | | | "
        f"**{total_zero}** | **{total_failed}** |"
    )
    report_lines.append("")
    report_lines.append(f"Tiempo total: {elapsed:.1f}s")

    if all_zero_chunk_files:
        report_lines.append("")
        report_lines.append("## Archivos con 0 chunks (revisar)")
        for item in all_zero_chunk_files:
            report_lines.append(f"- `{item['file']}` (document_id={item['document_id']})")

    if all_failed_files:
        report_lines.append("")
        report_lines.append("## Archivos fallidos (revisar)")
        for item in all_failed_files:
            report_lines.append(f"- `{item['file']}`: {item['error']}")

    # The manifest is the authoritative declaration of which run produced this
    # corpus: which client, which documentation version, when. Without it the
    # per-module JSONs are a pile of chunks with no provenance.
    # || El manifiesto es la declaración autoritativa de qué corrida produjo
    # este corpus: qué cliente, qué versión de la documentación, cuándo. Sin él
    # los JSON por módulo son una pila de chunks sin procedencia.
    manifest = CorpusManifest(
        corpus_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        doc_version=doc_version,
        generated_at=datetime.now(UTC),
        source_root=str(root),
        modules=sorted(modules),
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_tokens=total_tokens,
    )
    (out_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    report_path = out_dir / "chunking_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print()
    print(f"Total: {total_files} archivos -> {total_chunks} chunks, {total_tokens} tokens en {elapsed:.1f}s")
    print(f"0 chunks: {total_zero} | fallidos: {total_failed}")
    print(f"Reporte: {report_path}")
    print(f"Tenant/version: {tenant_id} / {doc_version}  (manifest.json)")


if __name__ == "__main__":
    main()
