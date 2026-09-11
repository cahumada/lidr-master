"""POST /answer — retrieve, then synthesize a cited response.

``POST`` and not ``GET``: a completion costs money, is not a cacheable lookup,
and the body can grow with filters. The retrieval call is the same
``HybridRetriever.retrieve(...)`` that ``GET /search`` already runs.

The router is transport: settings → filters → retriever → ``generate_answer``.
No prompt, no LLM call, no grounding check lives here.

|| ``POST /answer`` — recuperar, y después sintetizar una respuesta citada.
``POST`` y no ``GET``: una completion cuesta dinero, no es una consulta
cacheable, y el body puede crecer con filtros. La llamada de recuperación es
el mismo ``HybridRetriever.retrieve(...)`` que ya corre ``GET /search``.

El router es transporte: settings → filters → retriever → ``generate_answer``.
Acá no vive ni el prompt, ni la llamada al LLM, ni el chequeo de grounding.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_embedder, get_reranker, resolve_navigation_tree
from app.domain.business_db_store import resolve_active_run
from app.domain.profiles import ProfileResolutionError, synthesizer_runtime
from app.foundation.persistence.database import get_async_session
from app.foundation.persistence.usage import PURPOSE_ANSWER, llm_with_accounting
from app.generation.rag.answer import generate_answer
from app.generation.rag.context_budget import StatusResolver
from app.generation.rag.retrieval.hybrid import ALL_BRANCHES, DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.schemas import AnswerRequest, AnswerResponse
from app.generation.rag.store.repository import ChunkRepository, SearchFilters

router = APIRouter(prefix="/answer", tags=["answer"])


@router.post("", response_model=AnswerResponse)
async def answer(
    body: AnswerRequest,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> AnswerResponse:
    """A cited answer to ``body.question``, grounded in the retrieved chunks.

    || Una respuesta citada a ``body.question``, anclada en los chunks recuperados.
    """
    # Memory lives on the agentic path, which has the planner that resolves a
    # referential question before retrieval. This endpoint is the single-shot
    # one -- it is what the fidelity eval calls -- and has no planner to give
    # the session to. Rejecting is the only honest option: accepting the field
    # and ignoring it would answer without memory while the caller believed
    # otherwise, which is the silent behavior this codebase does not allow.
    # || La memoria vive en el camino agéntico, que tiene el planner que
    # resuelve una pregunta referencial antes de recuperar. Este endpoint es el
    # de un solo tiro —es el que llama el eval de fidelidad— y no tiene planner
    # al que darle la sesión. Rechazar es lo único honesto: aceptar el campo e
    # ignorarlo respondería sin memoria mientras quien llama cree lo contrario.
    if body.session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="POST /answer has no conversation memory. Use POST /answer/agentic "
            "or /answer/agentic/start with `session_id`. "
            "|| POST /answer no tiene memoria de conversación. Usar POST /answer/agentic "
            "o /answer/agentic/start con `session_id`.",
        )

    settings = get_settings()
    filters = SearchFilters(
        settings.TENANT_ID,
        settings.DOC_VERSION,
        module_code=body.module_code,
        window_type_name=body.window_type_name,
    )
    retriever = HybridRetriever(ChunkRepository(session), get_embedder())
    # The synthesizer's profile, if somebody configured one in the console.
    # Resolved here and not inside `generate_answer` so the eval script keeps
    # calling the same function with an explicit LLM and no database.
    # || El perfil del sintetizador, si alguien configuró uno en la consola. Se
    # resuelve acá y no dentro de `generate_answer` para que el script de eval
    # siga llamando a la misma función con un LLM explícito y sin base.
    try:
        runtime = await synthesizer_runtime(
            session, settings, profile_id=body.profile_id
        )
    except ProfileResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail
        ) from exc
    llm = llm_with_accounting(
        runtime.llm,
        purpose=PURPOSE_ANSWER,
        provider_id=runtime.provider_id,
        tenant_id=settings.TENANT_ID,
    )
    return await generate_answer(
        body.question,
        filters=filters,
        retriever=retriever,
        llm=llm,
        limit=body.limit,
        max_per_document=body.max_per_document,
        branches=ALL_BRANCHES if body.lexical else DEFAULT_BRANCHES,
        decompose_query=body.split,
        reranker=get_reranker() if body.rerank else None,
        persona=runtime.persona,
        guardrails=runtime.guardrails,
        # The window-status warning comes from the ACTIVE run's tree, not from
        # the stamped column. Resolved here because this is where the session
        # is; `generate_answer` takes it as a parameter for exactly that reason.
        # || La advertencia de estado sale del árbol de la corrida ACTIVA y no de
        # la columna estampada. Se resuelve acá porque acá está la sesión.
        status_of=await _status_of(session, settings),
    )


async def _status_of(session: AsyncSession, settings) -> StatusResolver | None:
    """The active run's status resolver, or nothing when no run is active.

    || El resolver de estado de la corrida activa, o nada si no hay ninguna.
    """
    active = await resolve_active_run(session, settings)
    if not active.run_id:
        return None
    tree = resolve_navigation_tree(active.env, active.run_id)
    return tree.window_status if tree is not None else None
