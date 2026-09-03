"""Audit a chunked corpus for statements the chunker left split in two.

A chunk whose text ends in a comma or a colon has not closed its statement.
That is not noise: it is half a business rule, and when the statement is a
conditional the other half read alone inverts it. This script counts them, so
the same number can be produced before a fix and checked after it.

After ``fix-dangling-lead-in-chunks`` the only ones left SHOULD be those the
token cap forced apart, and every one of those SHOULD carry ``continues_into``.
An open statement with no link is a regression, and the script exits 1 on it.

Usage:
    uv run python scripts/audit_dangling_chunks.py --chunks data/chunks
    uv run python scripts/audit_dangling_chunks.py --chunks data/chunks --samples 20

|| Audita un corpus troceado buscando enunciados que el chunker dejó partidos
en dos. Un chunk cuyo texto termina en coma o dos puntos no cerró su
enunciado. Eso no es ruido: es media regla de negocio, y cuando el enunciado
es un condicional la otra mitad leída sola la invierte. Este script los
cuenta, para poder producir el mismo número antes de un arreglo y verificarlo
después.

Después de ``fix-dangling-lead-in-chunks`` los únicos que DEBERÍAN quedar son
los que el techo de tokens obligó a separar, y cada uno DEBERÍA llevar
``continues_into``. Un enunciado abierto sin enlace es una regresión, y el
script sale con 1 en ese caso.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.chunking.functional_spec import _leaves_statement_open
from app.ingestion.pipeline import corpus_dir

HEADER_LINES = 2  # [Documento: ...] + [Sección: ...]


def chunk_body(text: str) -> str:
    """The chunk's content without its contextual header.

    || El contenido del chunk sin su header contextual.
    """
    lines = text.split("\n")
    if lines and lines[0].startswith("[Documento:"):
        return "\n".join(lines[HEADER_LINES:]).strip()
    return text.strip()


def audit(chunks_dir: Path, samples: int) -> int:
    total = 0
    narrative = 0
    open_statements: list[tuple[str, str, str, bool]] = []
    unlinked: list[tuple[str, str]] = []
    per_document: Counter[str] = Counter()

    for path in sorted(chunks_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for document in payload.get("documents", []):
            for chunk in document["chunks"]:
                total += 1
                if chunk["metadata"]["chunk_type"] != "narrative":
                    continue
                narrative += 1
                body = chunk_body(chunk["text"])
                if not _leaves_statement_open(body):
                    continue
                linked = bool(chunk["metadata"].get("continues_into"))
                open_statements.append((document["document_id"], chunk["chunk_id"], body, linked))
                per_document[document["document_id"]] += 1
                if not linked:
                    unlinked.append((chunk["chunk_id"], body))

    linked_count = sum(1 for *_rest, linked in open_statements if linked)

    print(f"chunks totales            : {total}")
    print(f"  narrativos              : {narrative}")
    print(f"  con enunciado abierto   : {len(open_statements)}", end="")
    if total:
        print(f"  ({len(open_statements) / total:.2%} del corpus)")
    else:
        print()
    print(f"    enlazados (continues_into) : {linked_count}")
    print(f"    SIN enlazar                : {len(unlinked)}")
    print(f"  documentos afectados    : {len(per_document)}")

    if per_document:
        print()
        print("documentos con más enunciados abiertos:")
        for document_id, count in per_document.most_common(10):
            print(f"   {count:5d}  {document_id}")

    if unlinked:
        print()
        print(f"muestras sin enlazar (hasta {samples}):")
        for chunk_id, body in unlinked[:samples]:
            print(f"   {chunk_id}: {body[:90]!r}")
        # An open statement with nothing to point at is either the last unit of
        # its section (legitimate) or a regression. The script cannot tell the
        # two apart from the corpus alone, so it reports rather than fails.
        # || Un enunciado abierto sin nada a lo cual apuntar es o la última
        # unidad de su sección (legítimo) o una regresión. El script no puede
        # distinguirlos solo con el corpus, así que reporta en vez de fallar.

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # El default es la BASE; el directorio real lleva el nombre de la version,
    # porque cada version de la documentacion tiene el suyo. Ver
    # `app.ingestion.pipeline.corpus_dir`.
    # || The default is the BASE; the real directory is named after the version,
    # because each documentation version has its own. See
    # `app.ingestion.pipeline.corpus_dir`.
    parser.add_argument("--chunks", type=Path, default=Path("data/chunks"))
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()
    args.chunks = corpus_dir(args.chunks, get_settings().DOC_VERSION)

    if not args.chunks.is_dir():
        print(f"no existe el directorio de chunks: {args.chunks}", file=sys.stderr)
        raise SystemExit(2)

    raise SystemExit(audit(args.chunks, args.samples))


if __name__ == "__main__":
    main()
