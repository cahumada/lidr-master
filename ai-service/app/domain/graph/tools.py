"""The single retrieval tool for ``evidence_retriever``.

Wraps ``HybridRetriever.retrieve`` exactly as ``/search`` and ``/answer`` use it —
no forked retrieval path.

|| La única herramienta de recuperación de ``evidence_retriever``. Envuelve
``HybridRetriever.retrieve`` tal cual lo usan ``/search`` y ``/answer``.
"""

from __future__ import annotations

from app.generation.rag.retrieval.hybrid import ALL_BRANCHES, DEFAULT_BRANCHES, HybridRetriever
from app.generation.rag.schemas import SearchHit, search_hits_from_chunks
from app.generation.rag.store.repository import SearchFilters


async def search_corpus(
    *,
    query: str,
    retriever: HybridRetriever,
    filters: SearchFilters,
    limit: int = 10,
    max_per_document: int | None = 1,
    lexical: bool = False,
    split: bool = True,
    reranker=None,
) -> tuple[list[SearchHit], str]:
    """Retrieve hits for ``query`` and return them with a short summary.

    || Recupera hits para ``query`` y los devuelve con un resumen corto.
    """
    result = await retriever.retrieve(
        query,
        filters,
        limit=limit,
        max_per_document=max_per_document,
        branches=ALL_BRANCHES if lexical else DEFAULT_BRANCHES,
        decompose_query=split,
        reranker=reranker,
    )
    hits = search_hits_from_chunks(result.chunks)
    summary = f"{len(hits)} hits for {query!r}"
    return hits, summary
