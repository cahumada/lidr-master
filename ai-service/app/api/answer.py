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

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_answer_llm, get_embedder, get_reranker
from app.foundation.persistence.database import get_async_session
from app.generation.rag.answer import generate_answer
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
    settings = get_settings()
    filters = SearchFilters(
        settings.TENANT_ID,
        settings.DOC_VERSION,
        module_code=body.module_code,
        window_type_name=body.window_type_name,
    )
    retriever = HybridRetriever(ChunkRepository(session), get_embedder())
    return await generate_answer(
        body.question,
        filters=filters,
        retriever=retriever,
        llm=get_answer_llm(),
        limit=body.limit,
        max_per_document=body.max_per_document,
        branches=ALL_BRANCHES if body.lexical else DEFAULT_BRANCHES,
        decompose_query=body.split,
        reranker=get_reranker() if body.rerank else None,
    )
