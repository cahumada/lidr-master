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

from app.config import get_settings
from app.foundation.llm.wrapper import LLM
from app.generation.rag.guardrails import check_grounding
from app.generation.rag.prompt_builder import build_budgeted_messages
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
    persona: str | None = None,
    guardrails: str | None = None,
) -> AnswerResponse:
    """Retrieve, generate, and mark whether the prose stayed inside the hits.

    ``persona`` and ``guardrails`` come from the ``answer_synthesizer``
    profile and are appended to the system prompt; ``None`` renders the
    prompt exactly as before, which is what keeps the fidelity eval
    comparable across runs that did not configure either.

    || Recupera, genera, y marca si la prosa se quedó dentro de los hits.
    ``persona`` y ``guardrails`` vienen del perfil y se appendean al system
    prompt; ``None`` deja el prompt como antes.
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

    system, user, budgeted = build_budgeted_messages(
        question,
        citations,
        budget=get_settings().ANSWER_MAX_CONTEXT_TOKENS,
        persona=persona,
        guardrails=guardrails,
    )

    # Evidence was retrieved and none of it fit. Treated as insufficient
    # context -- there is nothing to ground an answer on -- but reported with
    # `dropped_hits` set, which is what separates it from having found
    # nothing at all.
    # || Se recuperó evidencia y no entró ninguna. Se trata como contexto
    # insuficiente —no hay con qué anclar una respuesta— pero se reporta con
    # `dropped_hits`, que es lo que lo separa de no haber encontrado nada.
    if not budgeted.kept:
        log.warning(
            "answer_context_budget_exhausted",
            query=question,
            hits=len(citations),
            budget=budgeted.budget,
        )
        return AnswerResponse(
            question=question,
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            citations=[],
            grounded=True,
            context_truncated=True,
            dropped_hits=budgeted.dropped_count,
        )

    answer = llm.complete(system=system, user=user)
    # The prose is checked against what the model was actually shown, not
    # against everything the retriever found.
    # || La prosa se chequea contra lo que el modelo realmente vio, no contra
    # todo lo que encontró el retriever.
    grounding = check_grounding(answer, budgeted.kept)

    log.info(
        "answer",
        query=question,
        hits=len(budgeted.kept),
        dropped=budgeted.dropped_count,
        grounded=grounding.grounded,
        unsupported=grounding.unsupported_document_ids,
    )
    return AnswerResponse(
        question=question,
        answer=answer,
        citations=budgeted.kept,
        grounded=grounding.grounded,
        context_truncated=budgeted.truncated,
        dropped_hits=budgeted.dropped_count,
    )
