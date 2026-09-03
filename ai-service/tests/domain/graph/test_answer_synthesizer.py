"""Answer synthesizer agent tests.

|| Tests del agente answer_synthesizer.
"""

from __future__ import annotations

import asyncio

from app.domain.graph.agents.answer_synthesizer import answer_synthesizer
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE


class FakeLLM:
    def complete(self, *, system: str, user: str) -> str:
        return "Respuesta citada [CA014 · Validaciones]"


def test_empty_hits_skip_llm():
    state = {"query": "algo", "hits": [], "supervisor_steps": 3}
    config = {"configurable": {"llm": FakeLLM()}}
    update = asyncio.run(answer_synthesizer(state, config))
    assert update["answer"] == INSUFFICIENT_CONTEXT_MESSAGE


def test_hits_trigger_llm():
    state = {
        "query": "tope",
        "hits": [
            {
                "content_hash": "h1",
                "chunk_id": "CA014::Validaciones::0",
                "document_id": "CA014",
                "document_title": "t",
                "section": "Validaciones",
                "text": "texto",
                "score": 0.1,
            }
        ],
        "supervisor_steps": 3,
    }
    config = {"configurable": {"llm": FakeLLM()}}
    update = asyncio.run(answer_synthesizer(state, config))
    assert "CA014" in update["answer"]
