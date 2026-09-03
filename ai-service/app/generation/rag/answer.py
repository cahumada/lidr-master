"""Orchestrate one RAG answer: retrieve, prompt, complete, check.

Two consumers — ``POST /answer`` and ``scripts/eval_generation.py`` — so the
pipeline lives here and not in the router. The router stays transport; the
eval stays a measurement of the same function the endpoint calls.

|| Orquesta una respuesta RAG: recuperar, armar prompt, completar, chequear.
Dos consumidores — ``POST /answer`` y ``scripts/eval_generation.py`` — así
que el pipeline vive acá y no en el router. El router se queda en transporte;
el eval se queda midiendo la misma función que llama el endpoint.
"""

from __future__ import annotations

import structlog

from app.foundation.llm.wrapper import LLM
from app.generation.rag.guardrails import check_grounding
from app.generation.rag.prompt_builder import build_messages
from app.generation.rag.retrieval.hybrid import DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.schemas import AnswerResponse, search_hits_from_chunks
from app.generation.rag.store.repository import SearchFilters

log = structlog.get_logger()

# Same sentence the system prompt tells the model to use. Returned verbatim
# when retrieval is empty, so "no context" does not cost a completion and
# cannot invent a citation.
# || La misma frase que el system prompt le dice al modelo que use. Se
# devuelve tal cual cuando la recuperación viene vacía, así "sin contexto"
# no cuesta una completion y no puede inventar una cita.
INSUFFICIENT_CONTEXT_MESSAGE = (
    "No hay información suficiente en la documentación recuperada para responder."
)


async def generate_answer(
    question: str,
    *,
    filters: SearchFilters,
    retriever: HybridRetriever,
    llm: LLM,
    limit: int = 10,
    max_per_document: int | None = 1,
    branches: tuple[str, ...] = DEFAULT_BRANCHES,
    decompose_query: bool = True,
    reranker=None,
) -> AnswerResponse:
    """Retrieve, generate, and mark whether the prose stayed inside the hits.

    || Recupera, genera, y marca si la prosa se quedó dentro de los hits.
    """
    result = await retriever.retrieve(
        question,
        filters,
        limit=limit,
        max_per_document=max_per_document,
        branches=branches,
        decompose_query=decompose_query,
        reranker=reranker,
    )
    citations = search_hits_from_chunks(result.chunks)

    if not citations:
        log.info("answer_insufficient_context", query=question)
        return AnswerResponse(
            question=question,
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            citations=[],
            grounded=True,
        )

    system, user = build_messages(question, citations)
    answer = llm.complete(system=system, user=user)
    grounding = check_grounding(answer, citations)

    log.info(
        "answer",
        query=question,
        hits=len(citations),
        grounded=grounding.grounded,
        unsupported=grounding.unsupported_document_ids,
    )
    return AnswerResponse(
        question=question,
        answer=answer,
        citations=citations,
        grounded=grounding.grounded,
    )
