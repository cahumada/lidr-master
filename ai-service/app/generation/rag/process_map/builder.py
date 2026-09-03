"""Assemble the map from its three sources.

|| Arma el mapa desde sus tres fuentes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from app.generation.rag.navigation import ROOT_CODE, NavigationTree
from app.generation.rag.process_map.graph import Edge, ProcessMap, detect_cycles
from app.generation.rag.process_map.requisites import SECTION_PREFIX, extract_precedence

logger = structlog.get_logger(__name__)

# A sibling document referenced by its exported HTML filename, the way the
# corpus links: `[Campos](ma5571.html)`.
# || Un documento hermano referenciado por su nombre de archivo HTML exportado,
# como enlaza el corpus.
_HTML_LINK = re.compile(r"\[[^\]]*\]\(([^)]*?)\.html[^)]*\)", re.IGNORECASE)


def load_documents(chunks_dir: Path) -> dict[str, dict]:
    """Every document that produced chunks, by code.

    Documents with zero chunks are left out: ``MBC501`` is a `.md` that is
    actually UTF-16 HTML, a corrupt export, and it has nothing to relate.

    || Cada documento que produjo chunks, por código. Los documentos con cero
    chunks quedan afuera: ``MBC501`` es un `.md` que en realidad es HTML en
    UTF-16, un export corrupto, y no tiene nada que relacionar.
    """
    documents: dict[str, dict] = {}
    for path in sorted(chunks_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for document in payload["documents"]:
            if document["chunks"]:
                documents[document["document_id"].upper()] = document
    return documents


def _first_metadata(document: dict, key: str):
    for chunk in document["chunks"]:
        value = chunk["metadata"].get(key)
        if value:
            return value
    return None


def build(documents: dict[str, dict], tree: NavigationTree | None) -> ProcessMap:
    """The map: nodes from both sources, edges from three.

    || El mapa: nodos de las dos fuentes, aristas de las tres.
    """
    process_map = ProcessMap()
    known = set(documents)

    # --- Nodes from the documents || Nodos de los documentos ----------------
    for code, document in documents.items():
        node = process_map.node(code)
        node.has_document = True
        node.title = document.get("document_title")
        node.transaction_type = document.get("transaction_type") or _first_metadata(
            document, "transaction_type"
        )
        node.document_kind = document.get("document_kind") or _first_metadata(
            document, "document_kind"
        )
        node.module_code = _first_metadata(document, "module_code")
        node.module_name = _first_metadata(document, "module_name")

    # --- Nodes and hierarchy from the window tree || Nodos y jerarquía -------
    if tree is not None:
        for code in tree.codes():
            node = process_map.node(code)
            node.in_window_tree = True
            node.window_description = tree.description_of(code)
            parent = tree.parent_of(code)
            if parent:
                process_map.edges.append(
                    Edge(source=code, target=parent, edge_type="menu_parent",
                         origin="windows_tree")
                )
        # Unreachable means its path does not REACH the root, not merely that
        # it has no parent: 3 codes have no parent but do have children, and
        # every descendant of those is just as unreachable from the menu as
        # they are. `path()` already resolves this, and is cycle-safe.
        # || Inalcanzable significa que su camino no LLEGA a la raíz, no
        # simplemente que no tiene padre: 3 códigos no tienen padre pero sí
        # hijos, y cada descendiente de esos es tan inalcanzable desde el menú
        # como ellos. `path()` ya resuelve esto, y es a prueba de ciclos.
        for code in tree.codes():
            chain = tree.path(code)
            if not chain or chain[0] != ROOT_CODE:
                process_map.node(code).unreachable_from_menu = True

    # --- Declared precedence || Precedencia declarada ------------------------
    for code, document in documents.items():
        requisitos = [
            chunk
            for chunk in document["chunks"]
            if (chunk["metadata"].get("section") or "").lower().startswith(SECTION_PREFIX)
        ]
        precedence = extract_precedence(code, requisitos, known_documents=known)
        if precedence is None:
            continue
        process_map.coverage.precedence_declared += 1
        if precedence.unresolved:
            process_map.coverage.precedence_unresolved += 1
            process_map.unresolved_precedence.append((code, precedence.evidence))
            continue
        for target in precedence.requires:
            process_map.edges.append(
                Edge(source=code, target=target, edge_type="requires",
                     origin="requisitos_section", evidence=precedence.evidence)
            )

    # --- Cross references || Referencias cruzadas ----------------------------
    seen_references: set[tuple[str, str]] = set()
    for code, document in documents.items():
        # An index document's links are a table of contents, not a business
        # relation. Marked so a consumer can tell them apart.
        # || Los enlaces de un documento índice son una tabla de contenidos, no
        # una relación de negocio. Se marcan para poder distinguirlos.
        is_index = (document.get("document_kind") or _first_metadata(document, "document_kind")) == "index"
        origin = "index_document" if is_index else "chunk_reference"
        for chunk in document["chunks"]:
            for match in _HTML_LINK.finditer(chunk["text"]):
                target = match.group(1).rsplit("/", 1)[-1].upper()
                if target == code or target not in known:
                    continue
                if (code, target) in seen_references:
                    continue
                seen_references.add((code, target))
                process_map.edges.append(
                    Edge(source=code, target=target, edge_type="references", origin=origin)
                )

    # --- Coverage: what the map does NOT cover || Lo que el mapa NO cubre ----
    coverage = process_map.coverage
    coverage.nodes = len(process_map.nodes)
    coverage.documents = len(documents)
    coverage.window_codes = len(tree) if tree is not None else 0
    coverage.unreachable_from_menu = sum(
        1 for node in process_map.nodes.values() if node.unreachable_from_menu
    )
    coverage.window_codes_without_document = sum(
        1 for node in process_map.nodes.values() if node.in_window_tree and not node.has_document
    )
    coverage.documents_that_are_not_windows = sum(
        1 for node in process_map.nodes.values() if node.has_document and not node.in_window_tree
    )

    cycles = detect_cycles(process_map.edges, "menu_parent")
    coverage.cycles_detected = len(cycles)
    if cycles:
        logger.warning("process_map_cycles", count=len(cycles), sample=cycles[0])

    return process_map


def to_json(process_map: ProcessMap) -> dict:
    """The reproducible artifact: nodes, edges and coverage.

    || El artefacto reproducible: nodos, aristas y cobertura.
    """
    return {
        "coverage": process_map.coverage.as_dict(),
        "unresolved_precedence": [
            {"document_id": code, "evidence": evidence}
            for code, evidence in sorted(process_map.unresolved_precedence)
        ],
        "nodes": [
            {k: v for k, v in vars(node).items() if v not in (None, False)}
            for node in sorted(process_map.nodes.values(), key=lambda n: n.code)
        ],
        "edges": [
            {k: v for k, v in vars(edge).items() if v != ""}
            for edge in sorted(
                process_map.edges, key=lambda e: (e.edge_type, e.source, e.target)
            )
        ],
    }
