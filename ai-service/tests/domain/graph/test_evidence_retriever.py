"""Evidence retriever agent tests.

|| Tests del agente evidence_retriever.
"""

from __future__ import annotations

import asyncio

from app.domain.graph.agents.evidence_retriever import evidence_retriever
from app.generation.rag.retrieval.hybrid import RetrievalResult, RetrievedChunk


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def retrieve(self, query, filters, **kwargs):
        self.calls.append({"query": query, "filters": filters, **kwargs})
        return RetrievalResult(chunks=self.chunks, branch_counts={}, identifier_terms=[])


class PerQueryRetriever:
    """Answers each sub-query with its own list. || Responde cada subconsulta con su lista."""

    def __init__(self, by_query):
        self.by_query = by_query
        self.calls = []

    async def retrieve(self, query, filters, **kwargs):
        self.calls.append(query)
        return RetrievalResult(
            chunks=self.by_query.get(query, []), branch_counts={}, identifier_terms=[]
        )


def _chunk(content_hash: str, document_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        content_hash=content_hash,
        chunk_id=f"{document_id}::Validaciones::0",
        document_id=document_id,
        document_title="Coberturas",
        section="Validaciones",
        bullet_path=None,
        module_code=document_id[:2],
        document_kind="content",
        text="texto",
        score=0.1,
        branches=["vector"],
        ranks={"vector": 1},
    )


def test_search_corpus_writes_hits():
    chunk = RetrievedChunk(
        content_hash="h1",
        chunk_id="CA014::Validaciones::0",
        document_id="CA014",
        document_title="Coberturas",
        section="Validaciones",
        bullet_path=None,
        module_code="CA",
        document_kind="content",
        text="texto",
        score=0.1,
        branches=["vector"],
        ranks={"vector": 1},
    )
    fake = FakeRetriever([chunk])
    state = {
        "query": "tope de capital",
        "sub_queries": ["tope de capital"],
        "supervisor_steps": 2,
        "retrieval_options": {"limit": 5, "lexical": False, "split": False, "rerank": False},
    }
    config = {"configurable": {"retriever": fake, "reranker": None}}
    update = asyncio.run(evidence_retriever(state, config))
    assert len(update["hits"]) == 1
    assert update["hits"][0]["document_id"] == "CA014"
    assert fake.calls[0]["query"] == "tope de capital"


def _run_with_sub_queries(by_query: dict) -> dict:
    state = {
        "query": " y ".join(by_query),
        "sub_queries": list(by_query),
        "supervisor_steps": 2,
        "retrieval_options": {"limit": 5, "lexical": False, "split": False, "rerank": False},
    }
    config = {"configurable": {"retriever": PerQueryRetriever(by_query), "reranker": None}}
    return asyncio.run(evidence_retriever(state, config))


def test_sub_query_results_are_interleaved_not_concatenated():
    """So a tight budget cannot erase one half of a compound question.

    || Para que un presupuesto ajustado no borre una mitad de una pregunta compuesta.
    """
    update = _run_with_sub_queries(
        {
            "que valida CA014": [_chunk("a0", "CA014"), _chunk("a1", "CA014")],
            "que reporta CO001": [_chunk("b0", "CO001"), _chunk("b1", "CO001")],
        }
    )

    assert [hit["content_hash"] for hit in update["hits"]] == ["a0", "b0", "a1", "b1"]


def test_one_sub_query_keeps_the_retriever_order():
    """A single ranked run is already ordered best-first.

    || Una sola corrida rankeada ya viene ordenada, la mejor primero.
    """
    update = _run_with_sub_queries(
        {"tope de capital": [_chunk("a0", "CA014"), _chunk("a1", "CA014")]}
    )

    assert [hit["content_hash"] for hit in update["hits"]] == ["a0", "a1"]


def test_a_chunk_found_by_two_sub_queries_is_not_duplicated():
    update = _run_with_sub_queries(
        {
            "que valida CA014": [_chunk("shared", "CA014")],
            "que reporta CA014": [_chunk("shared", "CA014"), _chunk("b1", "CO001")],
        }
    )

    assert [hit["content_hash"] for hit in update["hits"]] == ["shared", "b1"]
