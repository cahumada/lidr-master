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
from app.dependencies import business_db_for_run
from app.foundation.llm.wrapper import LLM, Usage
from app.foundation.persistence.prompts import save_prompt
from app.generation.rag.business_db.models import BusinessDbContext
from app.generation.rag.context_budget import StatusResolver
from app.generation.rag.guardrails import check_grounding
from app.generation.rag.prompt_builder import build_budgeted_messages
from app.generation.rag.retrieval.hybrid import DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.schemas import AnswerResponse, TokenUsage, search_hits_from_chunks
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
    status_of: StatusResolver | None = None,
    active_run_env: str | None = None,
    active_run_id: str | None = None,
) -> AnswerResponse:
    """Retrieve, generate, and mark whether the prose stayed inside the hits.

    ``persona`` and ``guardrails`` come from the ``answer_synthesizer``
    profile and are appended to the system prompt; ``None`` renders the
    prompt exactly as before, which is what keeps the fidelity eval
    comparable across runs that did not configure either.

    ``status_of`` resolves a document's window status from the ACTIVE mirror
    run. It is a parameter and not something this function looks up, because
    resolving the active run is a query and this function does not own a
    session — whoever does owns the decision. Passing nothing falls back to the
    stamped `window_status` column, which is what the eval scripts get.

    ``active_run_id`` / ``active_run_env`` are the same run, for the
    business-db block. Without a run there is no block — no fallback to the
    latest run or the CSV.

    || Recupera, genera, y marca si la prosa se quedó dentro de los hits.
    ``persona`` y ``guardrails`` vienen del perfil y se appendean al system
    prompt; ``None`` deja el prompt como antes. ``status_of`` resuelve el estado
    de ventana desde la corrida ACTIVA del mirror: es un parámetro y no algo que
    esta función busque, porque resolver la corrida es una consulta y esta
    función no es dueña de una sesión. Sin él se cae a la columna estampada, que
    es lo que reciben los scripts de eval.
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

    db_for = business_db_for_run(active_run_env, active_run_id)

    if not citations:
        log.info("answer_insufficient_context", query=question)
        return AnswerResponse(
            question=question,
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            citations=[],
            grounded=True,
            business_db=_empty_business_db(active_run_env, active_run_id),
        )

    system, user, budgeted, db_context = build_budgeted_messages(
        question,
        citations,
        budget=get_settings().ANSWER_MAX_CONTEXT_TOKENS,
        persona=persona,
        guardrails=guardrails,
        business_db_for=db_for,
        status_of=status_of,
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
            business_db=db_context or _empty_business_db(active_run_env, active_run_id),
        )

    completion = llm.complete(system=system, user=user)
    answer = completion.text
    # Stored right where it was sent. Reconstructing it later would show a
    # prompt that never existed: persona, guardrails, memory and the active run
    # all move between the answer and the moment someone looks at it.
    # || Guardado justo donde se envió. Reconstruirlo después mostraría un
    # prompt que nunca existió.
    settings = get_settings()
    prompt_id = save_prompt(
        tenant_id=settings.TENANT_ID,
        agent="answer",
        model=getattr(llm, "model", "?"),
        system_text=system,
        user_text=user,
        context_budget=budgeted.budget,
        retention_days=settings.ANSWER_PROMPT_RETENTION_DAYS,
    )
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
        answer_truncated=completion.truncated,
        unsupported=grounding.unsupported_document_ids,
    )
    return AnswerResponse(
        question=question,
        answer=answer,
        citations=budgeted.kept,
        grounded=grounding.grounded,
        context_truncated=budgeted.truncated,
        dropped_hits=budgeted.dropped_count,
        answer_truncated=completion.truncated,
        usage=_token_usage(completion.usage),
        business_db=db_context,
        prompt_id=prompt_id,
    )


def _empty_business_db(env: str | None, run_id: str | None) -> BusinessDbContext:
    """Accounting when there were no codes to resolve.

    || Contabilidad cuando no hubo códigos que resolver.
    """
    if not run_id:
        return BusinessDbContext.absent("no_active_run", env=env)
    return BusinessDbContext(run_id=run_id, env=env, complete=True, block_emitted=False)


def _token_usage(usage: Usage) -> TokenUsage:
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        reported=usage.reported,
    )
