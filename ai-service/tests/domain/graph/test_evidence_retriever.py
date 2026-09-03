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
