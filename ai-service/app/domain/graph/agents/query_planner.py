"""Query planning agent — deterministic decomposition, zero tools.

|| Agente de planificación de consulta — descomposición determinista, cero tools.
"""

from __future__ import annotations

import re
from time import perf_counter

import structlog

from app.domain.graph.privilege import record_model_action
from app.domain.schemas import AnswerAgentState, QueryFilters
from app.generation.conversation.models import ConversationFacts
from app.generation.conversation.resolver import resolve
from app.generation.rag.retrieval.decomposition import decompose

log = structlog.get_logger()

_TRANSACTION_PREFIX = re.compile(r"^([A-Za-z]{2,4})\d", re.IGNORECASE)


def _suggest_filters(query: str) -> QueryFilters:
    """Heuristic filter hints from transaction-shaped tokens in the query.

    || Pistas heurísticas de filtros a partir de tokens con forma de transacción.
    """
    filters: QueryFilters = {}
    module_codes: list[str] = []
    for token in re.split(r"[\s,;:()\[\]¿?¡!\"']+", query):
        match = _TRANSACTION_PREFIX.match(token.strip("."))
        if match:
            code = match.group(1).upper()
            if code not in module_codes:
                module_codes.append(code)
    if module_codes:
        filters["module_code"] = module_codes
    return filters


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
    filters = _suggest_filters(resolved.text)
    filters = _apply_anchors(filters, state)

    contribution = record_model_action(
        "query_planner",
        "plan_query",
        step=step,
        summary=(
            f"{len(sub_queries)} sub-queries; filters={filters or '{}'}"
            + (f"; resolved with {', '.join(resolved.substituted)}" if resolved.rewritten else "")
        ),
        duration_ms=int((perf_counter() - started) * 1000),
    )
    log.info(
        "agent_query_planner",
        sub_queries=len(sub_queries),
        filters=filters,
        resolved=resolved.rewritten,
        referents=resolved.substituted,
    )
    return {
        "resolved_question": resolved.text,
        "resolved_referents": resolved.substituted,
        "sub_queries": sub_queries,
        "filters": filters,
        "agent_contributions": [contribution],
    }


def _facts_of(state: AnswerAgentState) -> ConversationFacts | None:
    """The session's facts, or ``None`` when the run has no session.

    || Los hechos de la sesión, o ``None`` si la corrida no tiene sesión.
    """
    raw = state.get("conversation_facts")
    if not raw:
        return None
    return ConversationFacts.model_validate(raw)


def _apply_anchors(filters: QueryFilters, state: AnswerAgentState) -> QueryFilters:
    """Add the pinned constraints to the filters this question suggested.

    A filter the question itself names wins: pinning "module CA" should not
    stop somebody from asking about DF explicitly in one turn. The anchor is
    a default, not a cage.

    || Agrega las restricciones fijadas a los filtros que sugirió la pregunta.
    Un filtro que la pregunta nombra gana: fijar «módulo CA» no debería
    impedir preguntar por DF explícitamente en un turno. El anchor es un
    default, no una jaula.
    """
    anchored = state.get("conversation_anchors") or []
    if not anchored:
        return filters

    pinned: dict[str, list[str]] = {}
    for anchor in anchored:
        kind = anchor.get("kind")
        value = anchor.get("value")
        if kind and value and value not in pinned.setdefault(kind, []):
            pinned[kind].append(value)

    merged: QueryFilters = dict(filters)
    for kind, values in pinned.items():
        if not merged.get(kind):
            merged[kind] = values
    return merged
