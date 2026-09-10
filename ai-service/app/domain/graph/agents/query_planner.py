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
    filters, sources = _resolve_filters(state, _suggest_filters(resolved.text))

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


def _resolve_filters(
    state: AnswerAgentState, suggested: QueryFilters
) -> tuple[QueryFilters, dict[str, str]]:
    """Resolve the three filter sources into one, and say where each came from.

    Precedence, per FIELD and not per block: ``request`` → ``question`` →
    ``anchor``. So a request that carries `module_code` and no
    `window_type_name` does not erase a window type the question or an anchor
    contributed.

    Why that order: of the three, the middle one is the only one that is not a
    statement of intent — it is a heuristic reading transaction-shaped tokens
    out of prose. A control the operator set for this turn beats that
    inference, which still beats a constraint pinned in an earlier turn: a
    filter the question itself names should not be blocked by a pin, because
    the anchor is a default, not a cage.

    || Resuelve las tres fuentes de filtros en una, y dice de dónde salió cada
    valor. Precedencia, por CAMPO y no por bloque: ``request`` → ``question``
    → ``anchor``. Así un request que trae `module_code` y no
    `window_type_name` no borra el tipo de ventana que aportó la pregunta o un
    anchor.

    Por qué ese orden: de las tres, la del medio es la única que NO es una
    declaración de intención — es una heurística que lee tokens con forma de
    transacción de un texto en prosa. Un control que el operador eligió para
    este turno le gana a esa inferencia, que sigue ganándole a una restricción
    fijada en un turno anterior: el anchor es un default, no una jaula.
    """
    pinned: dict[str, list[str]] = {}
    for anchor in state.get("conversation_anchors") or []:
        kind = anchor.get("kind")
        value = anchor.get("value")
        if kind and value and value not in pinned.setdefault(kind, []):
            pinned[kind].append(value)

    requested = state.get("request_filters") or {}
    by_precedence = (("request", requested), ("question", suggested), ("anchor", pinned))

    resolved: QueryFilters = {}
    sources: dict[str, str] = {}
    for field in ("module_code", "window_type_name"):
        for source, candidate in by_precedence:
            values = candidate.get(field)
            if values:
                resolved[field] = list(values)
                sources[field] = source
                break
    return resolved, sources
