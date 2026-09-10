"""Query planning agent — deterministic decomposition, zero tools.

|| Agente de planificación de consulta — descomposición determinista, cero tools.
"""

from __future__ import annotations

from time import perf_counter

import structlog

from app.domain.graph.privilege import record_model_action
from app.domain.schemas import AnswerAgentState, QueryFilters
from app.generation.conversation.models import ConversationFacts
from app.generation.conversation.resolver import resolve
from app.generation.rag.retrieval.decomposition import decompose

log = structlog.get_logger()

# The filter heuristic that used to live here is GONE, and it is worth saying
# why so nobody rebuilds it: it read a transaction-shaped token out of the
# question and used its prefix as a `module_code` (`CA014` -> "CA"). The corpus
# stores the `WINDOWS` module-node code there -- `DMECAR`, `DMECLI`, … -- so it
# narrowed to a module that does not exist and the question came back with zero
# evidence. Measured: "¿Qué valida CA014?" returned 0 citations, the same
# question without the code returned 5.
#
# It cannot be fixed by translating the prefix either: of 71 prefixes in the
# corpus, `OPL` spans five modules and `MA` four, so any mapping would have to
# pick one and drop the tail. And it was never needed -- `retrieval`'s
# exact-match branch already finds a named transaction by `document_id`.
#
# || La heurística de filtros que vivía acá SE FUE, y vale decir por qué para
# que nadie la reconstruya: usaba el prefijo de un código de transacción como
# `module_code` (`CA014` -> «CA»), y ahí el corpus guarda el código del nodo
# módulo de `WINDOWS` (`DMECAR`, `DMECLI`, …). Recortaba a un módulo inexistente
# y la pregunta volvía sin evidencia. Medido: «¿Qué valida CA014?» devolvía 0
# citas y la misma pregunta sin el código devolvía 5. Tampoco se arregla
# traduciendo el prefijo: de 71 prefijos, `OPL` cae en cinco módulos y `MA` en
# cuatro. Y nunca hizo falta: la rama de coincidencia exacta de `retrieval` ya
# encuentra una transacción nombrada por su `document_id`.


async def query_planner(state: AnswerAgentState) -> dict:
    """Split compound questions and suggest retrieval filters.

    || Parte preguntas compuestas y sugiere filtros de recuperación.
    """
    step = int(state.get("supervisor_steps") or 0)
    query = state.get("query") or ""
    started = perf_counter()

    # Resolve BEFORE decomposing. A referential follow-up split into
    # sub-questions is two unretrievable questions instead of one; naming the
    # subject first is what makes the split mean anything.
    # || Resolver ANTES de descomponer. Una pregunta de seguimiento
    # referencial partida en subpreguntas son dos preguntas imposibles de
    # buscar en vez de una; nombrar el sujeto primero es lo que hace que la
    # división signifique algo.
    facts = _facts_of(state)
    resolved = resolve(query, facts)

    sub_queries = decompose(resolved.text)
    if not sub_queries:
        sub_queries = [resolved.text]
    filters, sources = _resolve_filters(state)

    contribution = record_model_action(
        "query_planner",
        "plan_query",
        step=step,
        summary=(
            f"{len(sub_queries)} sub-queries; filters={_describe_filters(filters, sources)}"
            + (f"; resolved with {', '.join(resolved.substituted)}" if resolved.rewritten else "")
        ),
        duration_ms=int((perf_counter() - started) * 1000),
    )
    log.info(
        "agent_query_planner",
        sub_queries=len(sub_queries),
        filters=filters,
        filter_sources=sources,
        resolved=resolved.rewritten,
        referents=resolved.substituted,
    )
    return {
        "resolved_question": resolved.text,
        "resolved_referents": resolved.substituted,
        "sub_queries": sub_queries,
        "filters": filters,
        "filter_sources": sources,
        "agent_contributions": [contribution],
    }


def _describe_filters(filters: QueryFilters, sources: dict[str, str]) -> str:
    """Filters with the source of each one, for the audit trail.

    The value alone does not say why it applied, and with three possible
    sources that is the part somebody debugging needs.

    || Los filtros con la fuente de cada uno, para el rastro de auditoría. El
    valor solo no dice por qué se aplicó, y con tres fuentes posibles eso es
    justo lo que necesita quien está depurando.
    """
    if not filters:
        return "{}"
    return ", ".join(
        f"{field}={values} ({sources.get(field, 'unknown')})" for field, values in filters.items()
    )


def _facts_of(state: AnswerAgentState) -> ConversationFacts | None:
    """The session's facts, or ``None`` when the run has no session.

    || Los hechos de la sesión, o ``None`` si la corrida no tiene sesión.
    """
    raw = state.get("conversation_facts")
    if not raw:
        return None
    return ConversationFacts.model_validate(raw)


def _resolve_filters(state: AnswerAgentState) -> tuple[QueryFilters, dict[str, str]]:
    """Resolve the two filter sources into one, and say where each came from.

    Precedence, per FIELD and not per block: ``request`` → ``anchor``. So a
    request that carries `module_code` and no `window_type_name` does not erase
    a window type an anchor contributed.

    Why that order: what the operator chose for THIS turn beats what they
    pinned in an earlier one — the anchor is a default, not a cage.

    There is no third source derived from the question's text any more; the
    comment above this function says why.

    || Resuelve las dos fuentes de filtros en una, y dice de dónde salió cada
    valor. Precedencia, por CAMPO y no por bloque: ``request`` → ``anchor``.
    Lo que el operador eligió para ESTE turno le gana a lo que fijó en uno
    anterior: el anchor es un default, no una jaula. Ya no hay una tercera
    fuente derivada del texto de la pregunta; el comentario de arriba dice por
    qué.
    """
    pinned: dict[str, list[str]] = {}
    for anchor in state.get("conversation_anchors") or []:
        kind = anchor.get("kind")
        value = anchor.get("value")
        if kind and value and value not in pinned.setdefault(kind, []):
            pinned[kind].append(value)

    requested = state.get("request_filters") or {}
    by_precedence = (("request", requested), ("anchor", pinned))

    resolved: QueryFilters = {}
    sources: dict[str, str] = {}
    for field in ("module_code", "window_type_name", "transaction_prefix"):
        for source, candidate in by_precedence:
            values = candidate.get(field)
            if values:
                resolved[field] = list(values)
                sources[field] = source
                break
    return resolved, sources
