"""GET /search — la recuperación completa detrás de un endpoint.

``GET`` y no ``POST``: una búsqueda no crea nada, es idempotente, y una URL con
la consulta adentro se comparte y se cachea. Los filtros van como query params
por lo mismo.

La respuesta lleva la procedencia de cada hit —documento, sección, breadcrumb y
de qué camino vino— porque estas son reglas de negocio de seguros y una
respuesta que no se puede verificar contra su documento no sirve.

|| ``GET`` and not ``POST``: a search creates nothing, it is idempotent, and a
URL with the query in it can be shared and cached. The filters are query params
for the same reason.

The response carries each hit's provenance -- document, section, breadcrumb and
which branch found it -- because these are insurance business rules and an answer
that cannot be checked against its document is not useful.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_embedder, get_reranker
from app.foundation.persistence.database import get_async_session
from app.generation.rag.retrieval.decomposition import decompose
from app.generation.rag.retrieval.hybrid import ALL_BRANCHES, DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.schemas import SearchHit, SearchResponse
from app.generation.rag.store.repository import ChunkRepository, SearchFilters

log = structlog.get_logger()

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(
        min_length=2,
        description="The question, in natural language or a transaction code. "
        "|| La pregunta, en lenguaje natural o un código de transacción.",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="How many results. || Cuántos resultados.",
    ),
    max_per_document: int | None = Query(
        default=1,
        ge=1,
        description="Cap of chunks per document. Default 1, measured: a question with several "
        "relevant documents cannot be answered with ten chunks of one of them. "
        "|| Tope de chunks por documento. Default 1, medido: una pregunta con varios "
        "documentos relevantes no se puede responder con diez chunks de uno solo.",
    ),
    module_code: str | None = Query(
        default=None, description="Restrict to one module, e.g. 'CA'. || Restringir a un módulo."
    ),
    window_type_name: str | None = Query(
        default=None,
        description="Restrict by window type, e.g. 'Masivo con encabezado'. "
        "|| Restringir por tipo de ventana.",
    ),
    lexical: bool = Query(
        default=False,
        description="Add the full-text branch. Off by default: measured, it takes hit@1 from "
        "77% to 48% while hit@10 stays at 94%. || Agregar el camino full-text. Apagado por "
        "default: medido, lleva el acierto@1 de 77% a 48% mientras el @10 se queda en 94%.",
    ),
    split: bool = Query(
        default=True,
        description="Split a compound question and add what the parts find. Never reorders, so "
        "it cannot make the answer worse. || Dividir una pregunta compuesta y agregar lo que "
        "encuentran las partes. Nunca reordena, así que no puede empeorar la respuesta.",
    ),
    rerank: bool = Query(
        default=True,
        description="Reorder the candidate set. Measured: p@10 from 0.140 to 0.171 and found "
        "rate from 86% to 94%, at 3x the latency. || Reordenar el candidato. Medido: p@10 de "
        "0,140 a 0,171 y hallazgo de 86% a 94%, a 3 veces la latencia.",
    ),
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> SearchResponse:
    """The chunks relevant to ``q``, with their provenance.

    || Los chunks relevantes a ``q``, con su procedencia.
    """
    settings = get_settings()
    filters = SearchFilters(
        settings.TENANT_ID,
        settings.DOC_VERSION,
        module_code=module_code,
        window_type_name=window_type_name,
    )
    retriever = HybridRetriever(ChunkRepository(session), get_embedder())

    result = await retriever.retrieve(
        q,
        filters,
        limit=limit,
        max_per_document=max_per_document,
        branches=ALL_BRANCHES if lexical else DEFAULT_BRANCHES,
        decompose_query=split,
        reranker=get_reranker() if rerank else None,
    )

    # Recomputed rather than threaded back out of the retriever: `decompose` is
    # pure and cheap, and returning it from `retrieve` would put a reporting
    # concern into the retrieval contract.
    # || Se recalcula en lugar de sacarlo del retriever: `decompose` es puro y
    # barato, y devolverlo desde `retrieve` metería una cuestión de reporte
    # dentro del contrato de recuperación.
    sub_queries = decompose(q) if split else []

    log.info(
        "search",
        query=q,
        hits=len(result.chunks),
        sub_queries=len(sub_queries),
        reranked=rerank,
    )

    return SearchResponse(
        query=q,
        hits=[
            SearchHit(
                content_hash=chunk.content_hash,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                section=chunk.section,
                bullet_path=chunk.bullet_path,
                module_code=chunk.module_code,
                text=chunk.text,
                score=chunk.score,
                branches=chunk.branches,
                ranks=chunk.ranks,
            )
            for chunk in result.chunks
        ],
        count=len(result.chunks),
        sub_queries=sub_queries,
        reranked=rerank,
        branch_counts=result.branch_counts,
        identifier_terms=result.identifier_terms,
    )
