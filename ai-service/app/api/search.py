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
from app.generation.rag.schemas import SearchFacets, SearchResponse, search_hits_from_chunks
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
    module_code: list[str] | None = Query(  # noqa: B008 — FastAPI's required DI idiom.
        default=None,
        description="Restrict to one or more modules, e.g. 'CA' or repeated "
        "'?module_code=CA&module_code=DF' for either. || Restringir a uno o varios "
        "módulos, ej. 'CA' o repetido para 'CA o DF'.",
    ),
    window_type_name: list[str] | None = Query(  # noqa: B008 — FastAPI's required DI idiom.
        default=None,
        description="Restrict by one or more window types, e.g. 'Masivo con encabezado'. "
        "Repeat the param for several, matched with OR. "
        "|| Restringir por uno o varios tipos de ventana. Repetir el parámetro para "
        "varios, con semántica OR.",
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
        hits=search_hits_from_chunks(result.chunks),
        count=len(result.chunks),
        sub_queries=sub_queries,
        reranked=rerank,
        branch_counts=result.branch_counts,
        identifier_terms=result.identifier_terms,
    )


@router.get("/facets", response_model=SearchFacets)
async def facets(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> SearchFacets:
    """The `module_code` and `window_type_name` values a filter can pick from.

    Neither is a fixed enum -- `module_code` runs from two-letter codes like
    `CA` to six-letter ones like `DMECAR`, and there is no lookup table -- so a
    caller that wants to offer them as choices has to ask the corpus, not
    hard-code a list.

    || Los valores de `module_code` y `window_type_name` de los que puede
    elegir un filtro. Ninguno es un enum fijo -- `module_code` va de códigos de
    dos letras como `CA` a otros de seis como `DMECAR`, y no hay tabla de
    referencia -- así que quien los quiera ofrecer como opciones tiene que
    preguntarle al corpus, no escribir una lista a mano.
    """
    settings = get_settings()
    filters = SearchFilters(settings.TENANT_ID, settings.DOC_VERSION)
    repository = ChunkRepository(session)
    modules = await repository.distinct_module_codes(filters)
    window_types = await repository.distinct_window_type_names(filters)
    return SearchFacets(modules=modules, window_types=window_types)
