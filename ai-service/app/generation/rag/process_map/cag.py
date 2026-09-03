"""Render the map as the context a CAG preloads.

A CAG only makes sense if what gets preloaded FITS. The size is measured with
the same tokenizer the chunker uses, never estimated from characters -- an
estimate that is wrong by 20% is the difference between fitting and being
truncated.

And it is never truncated silently: over the ceiling the build FAILS. Half a map
reads as a whole one, which is worse than not having it.

|| Renderiza el mapa como el contexto que precarga un CAG.

Un CAG solo tiene sentido si lo precargado ENTRA. El tamaño se mide con el mismo
tokenizador que usa el chunker, nunca se estima por caracteres — una estimación
errada en un 20% es la diferencia entre entrar y quedar truncado.

Y nunca se trunca en silencio: por encima del techo la construcción FALLA. Medio
mapa se lee como uno entero, que es peor que no tenerlo.
"""

from __future__ import annotations

from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.process_map.graph import ProcessMap


class ContextTooLargeError(RuntimeError):
    """The rendered context does not fit the configured ceiling.

    || El contexto renderizado no entra en el techo configurado.
    """


# The order to drop things in if it ever stops fitting, most expendable first.
# Written down rather than improvised later: the hierarchy and the precedence
# are exactly what a RAG CANNOT reconstruct by similarity, so they go last.
# || El orden en que recortar si algún día deja de entrar, lo más prescindible
# primero. Escrito ahora y no improvisado después: la jerarquía y la precedencia
# son justamente lo que un RAG NO puede reconstruir por similitud, así que son
# lo último.
DROP_ORDER = ("window_codes_without_document", "document_catalogue", "hierarchy", "precedence")


def render_limits(process_map: ProcessMap) -> str:
    """What the map covers and what it does not, for whoever reads it.

    Goes INSIDE the context, not beside it: a model that gets the map without
    its limits will answer that a transaction does not exist when what happens
    is that it is not in the menu.

    || Qué cubre el mapa y qué no, para quien lo lea. Va ADENTRO del contexto y
    no al lado: un modelo que reciba el mapa sin sus límites va a contestar que
    una transacción no existe cuando lo que pasa es que no está en el menú.
    """
    c = process_map.coverage
    return "\n".join(
        [
            "## Qué es este mapa y qué NO es",
            "",
            f"Cubre {c.nodes:,} transacciones de VisualTIME: {c.documents:,} con",
            f"documentación funcional y {c.window_codes:,} registradas como ventana.",
            "",
            "Tres relaciones, que NO significan lo mismo:",
            "",
            "- `menu_parent`: dónde vive la transacción en el menú. Es estructura.",
            "- `requires`: que hay que ejecutar una antes de otra. Es una afirmación",
            "  del documento, y solo existe donde el documento la declara.",
            "- `references`: que un documento menciona a otro. NO implica dependencia;",
            "  las que salen de un documento índice son tabla de contenidos.",
            "",
            "Límites que hay que tener en cuenta al responder:",
            "",
            f"- {c.unreachable_from_menu:,} transacciones no cuelgan de ningún menú. Existen",
            "  y son reales: se ejecutan desde código o desde otra transacción. Que una",
            "  transacción no esté en la jerarquía NO significa que no exista.",
            f"- {c.window_codes_without_document:,} ventanas no tienen documentación funcional.",
            f"- {c.documents_that_are_not_windows:,} documentos no son una ventana (procesos,",
            "  rutinas de cálculo, índices).",
            f"- Solo {c.precedence_declared:,} documentos declaran precedencia de ejecución, y",
            f"  {c.precedence_unresolved:,} de ellos sin nombrar un código. Fuera de eso, la",
            "  documentación NO dice en qué orden se ejecutan los procesos: si no hay una",
            "  arista `requires`, no se puede afirmar que exista un orden.",
            "",
            "No inventar relaciones que no estén acá.",
        ]
    )


def render_hierarchy(process_map: ProcessMap) -> str:
    """The menu tree, one line per edge. || El árbol de menú, una línea por arista."""
    lines = ["## Jerarquía de navegación (transacción < padre: descripción)", ""]
    for edge in sorted(process_map.edges_of("menu_parent"), key=lambda e: (e.target, e.source)):
        node = process_map.nodes.get(edge.source)
        description = (node.window_description or node.title or "") if node else ""
        lines.append(f"{edge.source}<{edge.target}:{description}")
    return "\n".join(lines)


def render_unreachable(process_map: ProcessMap) -> str:
    """The transactions no menu reaches. Information, not a gap.

    || Las transacciones que ningún menú alcanza. Información, no un hueco.
    """
    codes = sorted(n.code for n in process_map.nodes.values() if n.unreachable_from_menu)
    lines = [
        f"## Transacciones no alcanzables desde el menú ({len(codes):,})",
        "",
        "Existen como ventana y no cuelgan de ninguna opción de menú.",
        "",
    ]
    for code in codes:
        node = process_map.nodes[code]
        lines.append(f"{code}:{node.window_description or node.title or ''}")
    return "\n".join(lines)


def render_precedence(process_map: ProcessMap) -> str:
    """What must run before what, and what was declared without a target.

    || Qué tiene que correr antes de qué, y qué se declaró sin destino.
    """
    edges = process_map.edges_of("requires")
    by_source: dict[str, list[str]] = {}
    for edge in edges:
        by_source.setdefault(edge.source, []).append(edge.target)

    lines = [
        f"## Precedencia de ejecución declarada ({len(edges):,} dependencias)",
        "",
        "`A requiere: B, C` significa que el documento de A declara que B y C se",
        "deben ejecutar antes.",
        "",
    ]
    for source in sorted(by_source):
        lines.append(f"{source} requiere: {', '.join(sorted(by_source[source]))}")

    if process_map.unresolved_precedence:
        lines += [
            "",
            f"Declaran precedencia sin nombrar un código ({len(process_map.unresolved_precedence)}):",
            "",
        ]
        for code, evidence in sorted(process_map.unresolved_precedence):
            lines.append(f"{code}: {evidence}")
    return "\n".join(lines)


def render_catalogue(process_map: ProcessMap) -> str:
    """Code, title and type of every documented transaction.

    || Código, título y tipo de cada transacción documentada.
    """
    lines = ["## Catálogo de transacciones documentadas (código:título [tipo])", ""]
    for node in sorted(process_map.nodes.values(), key=lambda n: n.code):
        if not node.has_document:
            continue
        kind = f" [{node.transaction_type}]" if node.transaction_type else ""
        lines.append(f"{node.code}:{node.title or node.window_description or ''}{kind}")
    return "\n".join(lines)


def render(process_map: ProcessMap, *, max_tokens: int) -> tuple[str, int]:
    """The full preloadable context and its measured token count.

    || El contexto precargable completo y su cuenta de tokens medida.
    """
    context = "\n\n".join(
        [
            "# Mapa de procesos de VisualTIME",
            render_limits(process_map),
            render_hierarchy(process_map),
            render_unreachable(process_map),
            render_precedence(process_map),
            render_catalogue(process_map),
        ]
    )
    tokens = count_tokens(context)
    if tokens > max_tokens:
        raise ContextTooLargeError(
            f"the map renders to {tokens:,} tokens, {tokens - max_tokens:,} over the "
            f"{max_tokens:,} ceiling. Nothing was written: a truncated map reads as a "
            f"whole one. Drop in this order if needed: {', '.join(DROP_ORDER)}."
        )
    return context, tokens
