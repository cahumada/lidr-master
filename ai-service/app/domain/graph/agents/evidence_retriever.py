"""Evidence retrieval agent — one tool: ``search_corpus``.

|| Agente de recuperación de evidencia — una tool: ``search_corpus``.
"""

from __future__ import annotations

import structlog
from langchain_core.runnables import RunnableConfig

from app.config import get_settings
from app.domain.graph.privilege import SEARCH_CORPUS_TOOL, guarded_dispatch
from app.domain.graph.tools import search_corpus
from app.domain.schemas import AnswerAgentState, QueryFilters, RetrievalOptions
from app.generation.rag.context_budget import interleave_by_query
from app.generation.rag.schemas import SearchHit
from app.generation.rag.store.repository import SearchFilters

log = structlog.get_logger()


def _step_of(state: AnswerAgentState) -> int:
    return int(state.get("supervisor_steps") or 0)


def _filters_from_state(state: AnswerAgentState) -> SearchFilters:
    settings = get_settings()
    hints: QueryFilters = state.get("filters") or {}
    return SearchFilters(
        settings.TENANT_ID,
        settings.DOC_VERSION,
        module_code=hints.get("module_code"),
        window_type_name=hints.get("window_type_name"),
    )


def _options_from_state(state: AnswerAgentState) -> RetrievalOptions:
    return state.get("retrieval_options") or {}


async def evidence_retriever(state: AnswerAgentState, config: RunnableConfig) -> dict:
    """Retrieve corpus evidence for the planned queries.

    || Recupera evidencia del corpus para las consultas planificadas.
    """
    deps = (config.get("configurable") or {}) if config else {}
    retriever = deps.get("retriever")
    reranker = deps.get("reranker")
    if retriever is None:
        raise RuntimeError("evidence_retriever requires configurable.retriever")

    step = _step_of(state)
    options = _options_from_state(state)
    filters = _filters_from_state(state)
    was_requery = bool(state.get("requery_requested") and state.get("requery"))
    queries = [state.get("requery")] if was_requery else []
    if not queries:
        # The resolved question, not the written one: a referential follow-up
        # searched verbatim brings back whatever looks like it.
        # || La pregunta resuelta, no la escrita: una pregunta de seguimiento
        # referencial buscada tal cual trae lo que se le parezca.
        fallback = state.get("resolved_question") or state.get("query") or ""
        queries = list(state.get("sub_queries") or [fallback])

    # One list per sub-query, kept apart instead of merged on arrival. The
    # grouping is what lets the context budget bite every sub-query a little
    # rather than erasing the evidence of one of them entirely; merging here
    # would throw away the only place that information exists.
    # || Una lista por subconsulta, separadas en vez de unidas al llegar. Esa
    # agrupación es lo que permite que el presupuesto de contexto recorte un
    # poco de cada subconsulta en lugar de borrar entera la evidencia de una;
    # unirlas acá tiraría el único lugar donde ese dato existe.
    hit_groups: list[list[SearchHit]] = []
    contributions: list[dict] = []

    for query in queries:
        if not query:
            continue

        async def _execute(args: dict) -> dict:
            hits, summary = await search_corpus(
                query=args["query"],
                retriever=retriever,
                filters=filters,
                limit=int(options.get("limit", 10)),
                max_per_document=options.get("max_per_document", 1),
                lexical=bool(options.get("lexical", False)),
                split=bool(options.get("split", True)),
                reranker=reranker,
            )
            return {
                "ok": True,
                "hits": [hit.model_dump() for hit in hits],
                "summary": summary,
            }

        result, contribution = await guarded_dispatch(
            "evidence_retriever",
            SEARCH_CORPUS_TOOL,
            {"query": query, "filters": hints_dict(filters)},
            step=step,
            executor=_execute,
        )
        contributions.append(contribution)
        if result.get("ok", True):
            hit_groups.append(
                [SearchHit.model_validate(hit) for hit in (result.get("hits") or [])]
            )

    hits = interleave_by_query(hit_groups)
    log.info(
        "agent_evidence_retriever",
        queries=len(queries),
        groups=len(hit_groups),
        hits=len(hits),
    )
    return {
        "hits": [hit.model_dump() for hit in hits],
        "citations": [hit.model_dump() for hit in hits],
        "requery": None,
        "requery_requested": False,
        "pending_resynthesis": was_requery,
        "agent_contributions": contributions,
    }


def hints_dict(filters: SearchFilters) -> dict:
    """Serialize ``SearchFilters`` for audit digests.

    || Serializa ``SearchFilters`` para digests de auditoría.
    """
    return {
        "module_code": filters.module_code,
        "window_type_name": filters.window_type_name,
    }
