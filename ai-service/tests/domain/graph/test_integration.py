"""Integration: full graph with MemorySaver, pause and resume.

|| Integración: grafo completo con MemorySaver, pausa y resume.
"""

from __future__ import annotations

import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.domain.graph.build import build_answer_graph
from app.domain.graph.runner import initial_state
from app.foundation.llm.wrapper import Completion
from app.generation.conversation.anchors import detect_anchors
from app.generation.conversation.facts import facts_from_turn
from app.generation.conversation.models import ConversationSession, Turn
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE
from app.generation.rag.retrieval.hybrid import RetrievalResult, RetrievedChunk
from app.generation.rag.schemas import AnswerRequest


class FakeLLM:
    def complete(self, *, system: str, user: str) -> Completion:
        return Completion(text=INSUFFICIENT_CONTEXT_MESSAGE)


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


class ChunkRetriever:
    """Returns one chunk and records every query it was asked.

    || Devuelve un chunk y registra cada consulta que le pidieron.
    """

    def __init__(self, document_id: str = "CA014") -> None:
        self.document_id = document_id
        self.queries: list[str] = []

    async def retrieve(self, query, filters, **kwargs):
        self.queries.append(query)
        return RetrievalResult(
            chunks=[
                RetrievedChunk(
                    content_hash=f"h-{len(self.queries)}",
                    chunk_id=f"{self.document_id}::Validaciones::0",
                    document_id=self.document_id,
                    document_title="Coberturas",
                    section="Validaciones",
                    bullet_path=None,
                    module_code=self.document_id[:2],
                    document_kind="content",
                    text="El capital asegurado no puede superar el maximo del plan.",
                    score=0.1,
                    branches=["vector"],
                    ranks={"vector": 1},
                )
            ],
            branch_counts={},
            identifier_terms=[],
        )


class CitingLLM:
    def complete(self, *, system: str, user: str) -> Completion:
        return Completion(text="El tope aplica. [CA014 · Validaciones]")


def test_three_turns_of_one_conversation(monkeypatch):
    """The conversation this change exists for, end to end.

    Turn 1 asks about a transaction. Turn 2 only points at it, and has to be
    resolved before retrieval or the retriever searches "¿y eso?". Turn 3
    pins a module and every later retrieval carries it.

    || La conversación por la que existe este cambio, de punta a punta. El
    turno 2 solo señala, y hay que resolverlo antes de recuperar o el
    retriever busca «¿y eso?». El turno 3 fija un módulo y toda recuperación
    posterior lo lleva.
    """
    monkeypatch.setattr(
        "app.domain.graph.gate.get_settings",
        lambda: type("S", (), {"ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD": 0.6})(),
    )
    retriever = ChunkRetriever()
    graph = build_answer_graph(MemorySaver())
    conversation = ConversationSession()

    def _config(thread: str) -> dict:
        return {
            "configurable": {
                "thread_id": f"answer-agent:{thread}",
                "retriever": retriever,
                "llm": CitingLLM(),
                "reranker": None,
            }
        }

    def _body(question: str) -> AnswerRequest:
        return AnswerRequest(
            question=question,
            limit=5,
            split=False,
            rerank=False,
            session_id=conversation.session_id,
        )

    async def _turn(index: int, question: str) -> dict:
        body = _body(question)
        conversation.pin(detect_anchors(question))
        await graph.ainvoke(initial_state(body, conversation), _config(f"t{index}"))
        values = (await graph.aget_state(_config(f"t{index}"))).values
        cited = [hit["document_id"] for hit in values.get("citations") or []]
        conversation.facts = conversation.facts.merge_with(
            facts_from_turn(
                question=question,
                filters=dict(values.get("filters") or {}),
                cited_document_ids=cited,
            )
        )
        conversation.append_turn(
            Turn(
                question=question,
                resolved_question=values.get("resolved_question") or question,
                answer=values.get("answer") or "",
            ),
            max_turns=4,
        )
        return values

    async def _run():
        first = await _turn(1, "¿Qué valida CA014 al dar de alta?")
        assert first["resolved_question"] == first["query"]
        assert conversation.facts.last_document_ids == ["CA014"]

        second = await _turn(2, "¿y eso para siniestros?")
        # Resolved before retrieval: the retriever never saw the bare
        # reference. || Resuelta antes de recuperar: el retriever nunca vio la
        # referencia pelada.
        assert "CA014" in second["resolved_question"]
        assert second["resolved_question"] != second["query"]
        assert all("CA014" in query for query in retriever.queries)

        third = await _turn(3, "de acá en adelante, solo módulo CA: ¿qué reporta?")
        # `transaction_prefix` y no `module_code`: «módulo CA» significa las
        # transacciones que empiezan con CA, y el `module_code` del corpus es
        # `DMECAR`. Fijarlo como `module_code` dejaba este tercer turno —y
        # todos los siguientes— sin evidencia.
        assert third["filters"].get("transaction_prefix") == ["CA"]
        assert third["filter_sources"] == {"transaction_prefix": "anchor"}
        assert [(a.kind, a.value) for a in conversation.anchors] == [
            ("transaction_prefix", "CA")
        ]

    asyncio.run(_run())
