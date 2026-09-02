"""The graph: nodes are transactions, edges are three different relations.

The three are never collapsed. ``menu_parent`` says where a transaction lives in
the menu, ``requires`` says one must run before another, ``references`` says one
document mentions another. Merging them destroys what makes them useful: the
biggest emitters of ``references`` are index documents -- ``LIFE_INDEX`` with 130
-- so a consumer that read them as precedence would conclude that index has 130
process dependencies.

|| El grafo: los nodos son transacciones, las aristas tres relaciones distintas.

Las tres nunca se colapsan. Fusionarlas destruye lo que las hace útiles: los
mayores emisores de ``references`` son documentos índice —``LIFE_INDEX`` con
130— así que un consumidor que las leyera como precedencia concluiría que ese
índice tiene 130 dependencias de proceso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

EdgeType = Literal["menu_parent", "requires", "references"]

# Where an edge came from, so any of them can be audited back to its source.
# || De dónde salió una arista, así cualquiera se puede auditar hasta su fuente.
EdgeOrigin = Literal["windows_tree", "requisitos_section", "chunk_reference", "index_document"]


@dataclass(frozen=True)
class Edge:
    """One relation between two transactions.

    || Una relación entre dos transacciones.
    """

    source: str
    target: str
    edge_type: EdgeType
    origin: EdgeOrigin
    # The sentence that justified a `requires` edge. Empty for the others,
    # whose justification is structural.
    # || La oración que justificó una arista `requires`. Vacía para las otras,
    # cuya justificación es estructural.
    evidence: str = ""


@dataclass
class Node:
    """A transaction, as the map knows it.

    A node can exist with no document (1850 window codes have none) or with no
    window (672 documents are not a window). Both are real states of the
    system, not gaps to fill.

    || Una transacción, como la conoce el mapa. Un nodo puede existir sin
    documento (1850 códigos de ventana no lo tienen) o sin ventana (672
    documentos no son una ventana). Los dos son estados reales del sistema, no
    huecos que haya que llenar.
    """

    code: str
    title: str | None = None
    window_description: str | None = None
    module_code: str | None = None
    module_name: str | None = None
    transaction_type: str | None = None
    document_kind: str | None = None
    has_document: bool = False
    in_window_tree: bool = False
    # No parent in the export AND no children: a transaction that exists as a
    # window and is not reachable from any menu. 714 of them, and knowing which
    # is part of understanding the system.
    # || Sin padre en el export Y sin hijos: una transacción que existe como
    # ventana y no es alcanzable desde ningún menú. Son 714, y saber cuáles es
    # parte de entender el sistema.
    unreachable_from_menu: bool = False


@dataclass
class Coverage:
    """What the map does not cover, counted.

    A map that omitted these would read as complete and lead to claiming a
    transaction does not exist when what happens is it is not in the menu.

    || Lo que el mapa no cubre, contado. Un mapa que los omitiera se leería como
    completo y llevaría a afirmar que una transacción no existe cuando lo que
    pasa es que no está en el menú.
    """

    nodes: int = 0
    documents: int = 0
    window_codes: int = 0
    unreachable_from_menu: int = 0
    window_codes_without_document: int = 0
    documents_that_are_not_windows: int = 0
    precedence_declared: int = 0
    precedence_unresolved: int = 0
    cycles_detected: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(vars(self))


@dataclass
class ProcessMap:
    """Nodes, edges and what is not covered.

    || Nodos, aristas y lo que no está cubierto.
    """

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    # Documents that declared precedence without naming a resolvable code.
    # || Documentos que declararon precedencia sin nombrar un código resoluble.
    unresolved_precedence: list[tuple[str, str]] = field(default_factory=list)

    def edges_of(self, edge_type: EdgeType) -> list[Edge]:
        """Only the edges of one relation. || Solo las aristas de una relación."""
        return [edge for edge in self.edges if edge.edge_type == edge_type]

    def node(self, code: str) -> Node:
        """The node for ``code``, created on first mention.

        || El nodo de ``code``, creado en su primera mención.
        """
        if code not in self.nodes:
            self.nodes[code] = Node(code=code)
        return self.nodes[code]


def detect_cycles(edges: list[Edge], edge_type: EdgeType) -> list[list[str]]:
    """Cycles in one relation, so a consumer that walks it cannot hang.

    The window tree already contains two, so this is not hypothetical.

    || Ciclos en una relación, para que un consumidor que la recorra no cuelgue.
    El árbol de ventanas ya tiene dos, así que esto no es hipotético.
    """
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        if edge.edge_type == edge_type:
            outgoing.setdefault(edge.source, []).append(edge.target)

    cycles: list[list[str]] = []
    state: dict[str, int] = {}  # 0 = visiting, 1 = done

    def walk(start: str) -> None:
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            node, path = stack.pop()
            if state.get(node) == 1:
                continue
            state[node] = 0
            for target in outgoing.get(node, ()):
                if target in path:
                    cycles.append([*path[path.index(target) :], target])
                    continue
                if state.get(target) != 1:
                    stack.append((target, [*path, target]))
            state[node] = 1

    for node in list(outgoing):
        if state.get(node) != 1:
            walk(node)
    return cycles
