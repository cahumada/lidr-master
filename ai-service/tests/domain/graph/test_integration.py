"""Integration: full graph with MemorySaver, pause and resume.

|| Integración: grafo completo con MemorySaver, pausa y resume.
"""

from __future__ import annotations

import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.domain.graph.build import build_answer_graph
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE
from app.generation.rag.retrieval.hybrid import RetrievalResult


class FakeLLM:
    def complete(self, *, system: str, user: str) -> str:
        return INSUFFICIENT_CONTEXT_MESSAGE


class EmptyRetriever:
    async def retrieve(self, query, filters, **kwargs):
        return RetrievalResult(chunks=[], branch_counts={}, identifier_terms=[])


def test_out_of_corpus_question_pauses_then_resumes(monkeypatch):
    monkeypatch.setattr(
        "app.domain.graph.gate.get_settings",
        lambda: type("S", (), {"ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD": 0.6})(),
    )
    graph = build_answer_graph(MemorySaver())
    thread_id = "test-thread"
    config = {
        "configurable": {
            "thread_id": f"answer-agent:{thread_id}",
            "retriever": EmptyRetriever(),
            "llm": FakeLLM(),
            "reranker": None,
        }
    }
    state = {
        "query": "transacción inventada ZZ404 fuera del corpus",
        "retrieval_options": {
            "limit": 5,
            "max_per_document": 1,
            "lexical": False,
            "split": False,
            "rerank": False,
        },
        "supervisor_steps": 0,
        "retrieval_attempts": 0,
        "routing_history": [],
        "agent_contributions": [],
        "review_reasons": [],
    }

    async def _run():
        await graph.ainvoke(state, config)
        snapshot = await graph.aget_state(config)
        assert snapshot.next
        assert snapshot.interrupts
        reasons = snapshot.interrupts[0].value.get("reasons") or []
        assert reasons

        await graph.ainvoke(Command(resume={"decision": "approve", "note": "ok"}), config)
        final = await graph.aget_state(config)
        assert not final.next
        assert final.values.get("human_decision", {}).get("decision") == "approve"

    asyncio.run(_run())
