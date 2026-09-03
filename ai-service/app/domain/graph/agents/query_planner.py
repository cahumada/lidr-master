"""Query planning agent — deterministic decomposition, zero tools.

|| Agente de planificación de consulta — descomposición determinista, cero tools.
"""

from __future__ import annotations

import re
from time import perf_counter

import structlog

from app.domain.graph.privilege import record_model_action
from app.domain.schemas import AnswerAgentState, QueryFilters
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

    sub_queries = decompose(query)
    if not sub_queries:
        sub_queries = [query]
    filters = _suggest_filters(query)

    contribution = record_model_action(
        "query_planner",
        "plan_query",
        step=step,
        summary=f"{len(sub_queries)} sub-queries; filters={filters or '{}'}",
        duration_ms=int((perf_counter() - started) * 1000),
    )
    log.info(
        "agent_query_planner",
        sub_queries=len(sub_queries),
        filters=filters,
    )
    return {
        "sub_queries": sub_queries,
        "filters": filters,
        "agent_contributions": [contribution],
    }
