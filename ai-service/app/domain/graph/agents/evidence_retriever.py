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
        queries = list(state.get("sub_queries") or [state.get("query") or ""])

    all_hits: dict[str, SearchHit] = {}
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
            for hit in result.get("hits") or []:
                key = hit.get("content_hash") or hit.get("chunk_id") or str(hit)
                all_hits[key] = SearchHit.model_validate(hit)

    hits = list(all_hits.values())
    log.info("agent_evidence_retriever", queries=len(queries), hits=len(hits))
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
