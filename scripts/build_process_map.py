"""Build the process map and the context a CAG preloads.

Reads the chunked corpus and the window-tree export, assembles the graph from
three sources, writes the reproducible JSON artifact plus the preloadable
context, and loads the edges into Postgres so retrieval can expand along them.

Usage:
    uv run python scripts/build_process_map.py --dry-run
    uv run python scripts/build_process_map.py

|| Arma el mapa de procesos y el contexto que precarga un CAG.

Lee el corpus troceado y el export del árbol de ventanas, arma el grafo desde
tres fuentes, escribe el artefacto JSON reproducible más el contexto
precargable, y carga las aristas en Postgres para que la recuperación pueda
expandir por ellas.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

# Run as a script (not `python -m`), so add the repo root to sys.path.
# || Se corre como script (no `python -m`), así que se agrega la raíz del repo a sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.generation.rag.navigation import get_navigation_tree
from app.generation.rag.process_map.builder import build, load_documents, to_json
from app.generation.rag.process_map.cag import ContextTooLargeError, render
from app.ingestion.pipeline import corpus_dir

REPORT_FILENAME = "process_map_report.md"

_INSERT_SQL = """
INSERT INTO process_map_edges
    (tenant_id, doc_version, source, target, edge_type, origin, evidence)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (tenant_id, doc_version, source, target, edge_type) DO NOTHING
"""


def corpus_identity(chunks_dir: Path) -> tuple[str, str]:
    path = chunks_dir / "manifest.json"
    if not path.exists():
        return "unknown", "unknown"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return manifest.get("tenant_id", "unknown"), manifest.get("doc_version", "unknown")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # El default es la BASE; el directorio real lleva el nombre de la version,
    # porque cada version de la documentacion tiene el suyo. Ver
    # `app.ingestion.pipeline.corpus_dir`.
    # || The default is the BASE; the real directory is named after the version,
    # because each documentation version has its own. See
    # `app.ingestion.pipeline.corpus_dir`.
    parser.add_argument("--chunks", type=Path, default=Path("data/chunks"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and measure, writing nothing and connecting to nothing.",
    )
    parser.add_argument(
        "--skip-database", action="store_true", help="Write the artifacts, skip the load."
    )
    args = parser.parse_args()
    args.chunks = corpus_dir(args.chunks, get_settings().DOC_VERSION)

    settings = get_settings()
    tenant_id, doc_version = corpus_identity(args.chunks)

    documents = load_documents(args.chunks)
    if not documents:
        print(f"No chunked documents under {args.chunks}", file=sys.stderr)
        return 1
    tree = get_navigation_tree(settings.WINDOWS_TREE_PATH)

    process_map = build(documents, tree)
    by_type = collections.Counter(edge.edge_type for edge in process_map.edges)
    by_origin = collections.Counter(edge.origin for edge in process_map.edges)

    print(f"Tenant / version:   {tenant_id} / {doc_version}")
    print(f"Nodes:              {len(process_map.nodes):,}")
    print(f"Edges:              {len(process_map.edges):,}")
    for edge_type in ("menu_parent", "requires", "references"):
        print(f"  {edge_type:<18}{by_type[edge_type]:>7,}")
    print(f"Edge origins:       {dict(by_origin)}")
    print("\nWhat the map does NOT cover:")
    for key, value in process_map.coverage.as_dict().items():
        print(f"  {key:<38}{value:>7,}")

    # Rendered before anything is written, so an oversized context fails the
    # run instead of leaving a JSON artifact next to a missing context.
    # || Se renderiza antes de escribir nada, así un contexto sobredimensionado
    # hace fallar la corrida en vez de dejar un artefacto JSON al lado de un
    # contexto que falta.
    try:
        context, tokens = render(process_map, max_tokens=settings.CAG_MAX_TOKENS)
    except ContextTooLargeError as error:
        print(f"\n{error}", file=sys.stderr)
        return 1

    print(f"\nCAG context:        {tokens:,} tokens "
          f"({tokens / settings.CAG_MAX_TOKENS:.0%} of the {settings.CAG_MAX_TOKENS:,} ceiling)")

    if args.dry_run:
        print("\n--dry-run: nothing was written and nothing was connected to.")
        return 0

    settings.PROCESS_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.PROCESS_MAP_PATH.write_text(
        json.dumps(to_json(process_map), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    settings.CAG_CONTEXT_PATH.write_text(context, encoding="utf-8")
    (args.chunks / REPORT_FILENAME).write_text(
        render_report(process_map, tenant_id, doc_version, tokens, by_type, by_origin),
        encoding="utf-8",
    )
    print(f"Wrote               {settings.PROCESS_MAP_PATH}")
    print(f"Wrote               {settings.CAG_CONTEXT_PATH}")

    if args.skip_database:
        print("\n--skip-database: the edges were not loaded.")
        return 0

    # Imported here so --dry-run never needs a reachable database.
    # || Se importa acá para que --dry-run nunca necesite una base alcanzable.
    from app.foundation.persistence.database import get_engine

    raw = get_engine().raw_connection()
    try:
        connection = raw.driver_connection
        with connection.cursor() as cursor:
            cursor.executemany(
                _INSERT_SQL,
                [
                    (tenant_id, doc_version, e.source, e.target, e.edge_type, e.origin,
                     e.evidence or None)
                    for e in process_map.edges
                ],
            )
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM process_map_edges WHERE tenant_id = %s AND doc_version = %s",
                (tenant_id, doc_version),
            )
            stored = cursor.fetchone()[0]
    finally:
        raw.close()

    print(f"Edges in Postgres:  {stored:,}")
    return 0


def render_report(process_map, tenant_id, doc_version, tokens, by_type, by_origin) -> str:
    c = process_map.coverage
    lines = [
        "# Reporte del mapa de procesos",
        "",
        f"- Cliente / versión: `{tenant_id}` / `{doc_version}`",
        f"- Nodos: **{len(process_map.nodes):,}**",
        f"- Aristas: **{len(process_map.edges):,}**",
        f"- Contexto del CAG: **{tokens:,} tokens**",
        "",
        "## Aristas por tipo",
        "",
        "| tipo | cantidad | qué afirma |",
        "|---|---:|---|",
        f"| `menu_parent` | {by_type['menu_parent']:,} | dónde vive en el menú |",
        f"| `requires` | {by_type['requires']:,} | que hay que ejecutar una antes de otra |",
        f"| `references` | {by_type['references']:,} | que un documento menciona a otro |",
        "",
        "## Aristas por origen",
        "",
        "| origen | cantidad |",
        "|---|---:|",
    ]
    for origin, count in by_origin.most_common():
        lines.append(f"| `{origin}` | {count:,} |")
    lines += [
        "",
        "## Lo que el mapa NO cubre",
        "",
        "Ninguno de estos números es un error a corregir: es cómo es el sistema.",
        "Un mapa que los omitiera se leería como completo.",
        "",
        "| | |",
        "|---|---:|",
        f"| Transacciones no alcanzables desde ningún menú | {c.unreachable_from_menu:,} |",
        f"| Ventanas sin documentación funcional | {c.window_codes_without_document:,} |",
        f"| Documentos que no son una ventana | {c.documents_that_are_not_windows:,} |",
        f"| Documentos que declaran precedencia | {c.precedence_declared:,} |",
        f"| ...de ellos, sin nombrar un código | {c.precedence_unresolved:,} |",
        f"| Ciclos detectados en la jerarquía | {c.cycles_detected:,} |",
        "",
        "Fuera de los documentos que declaran precedencia, la documentación **no**",
        "dice en qué orden se ejecutan los procesos. Si no hay una arista",
        "`requires`, no se puede afirmar que exista un orden.",
    ]
    if process_map.unresolved_precedence:
        lines += ["", "## Precedencia declarada sin destino nombrable", ""]
        for code, evidence in sorted(process_map.unresolved_precedence):
            lines.append(f"- **{code}**: {evidence}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
