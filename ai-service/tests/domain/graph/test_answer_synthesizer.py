"""Answer synthesizer agent tests.

|| Tests del agente answer_synthesizer.
"""

from __future__ import annotations

import asyncio

import pytest

from app.config import get_settings
from app.domain.graph.agents.answer_synthesizer import answer_synthesizer
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE
from app.generation.rag.chunking.base import count_tokens
from app.generation.rag.context_budget import render_hit_block
from app.generation.rag.schemas import SearchHit


class FakeLLM:
    def complete(self, *, system: str, user: str) -> str:
        return "Respuesta citada [CA014 · Validaciones]"


class RefusingLLM:
    """Fails the test if the synthesizer calls it. || Falla el test si lo llaman."""

    def complete(self, *, system: str, user: str) -> str:  # pragma: no cover - must not run
        raise AssertionError("the LLM must not be called without context")


def _hit(index: int, text: str = "texto") -> dict:
    return {
        "content_hash": f"h{index}",
        "chunk_id": f"CA014::Validaciones::{index}",
        "document_id": "CA014",
        "document_title": "t",
        "section": "Validaciones",
        "text": text,
        "score": 0.1,
    }


@pytest.fixture
def budget(monkeypatch):
    """Set ANSWER_MAX_CONTEXT_TOKENS for one test. || Fija el presupuesto por test."""

    def _set(value: int) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "ANSWER_MAX_CONTEXT_TOKENS", value, raising=False)

    return _set


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


def test_citations_are_what_the_model_saw_not_what_was_retrieved(budget):
    """A chunk that never reached the prompt is not provenance.

    || Un chunk que nunca llegó al prompt no es procedencia.
    """
    hits = [_hit(index, text="regla de negocio " * 40) for index in range(5)]
    # Room for the first two blocks and not the third, measured the same way
    # the budget measures. || Espacio para los dos primeros bloques y no el
    # tercero, medido igual que lo mide el presupuesto.
    fits_two = sum(
        count_tokens(render_hit_block(position, SearchHit.model_validate(hit)))
        for position, hit in enumerate(hits[:2], start=1)
    )
    budget(fits_two)
    state = {"query": "tope", "hits": hits, "supervisor_steps": 3}

    update = asyncio.run(answer_synthesizer(state, {"configurable": {"llm": FakeLLM()}}))

    assert 0 < len(update["citations"]) < len(hits)
    assert update["context_truncated"] is True
    assert update["dropped_hits"] == len(hits) - len(update["citations"])


def test_a_budget_that_fits_everything_cites_everything(budget):
    hits = [_hit(index) for index in range(3)]
    budget(10_000)
    state = {"query": "tope", "hits": hits, "supervisor_steps": 3}

    update = asyncio.run(answer_synthesizer(state, {"configurable": {"llm": FakeLLM()}}))

    assert len(update["citations"]) == 3
    assert update["context_truncated"] is False
    assert update["dropped_hits"] == 0


def test_evidence_that_does_not_fit_skips_the_llm_and_stays_distinguishable(budget):
    """Same message as "no hits", told apart by dropped_hits.

    || El mismo mensaje que "sin hits", distinguible por dropped_hits.
    """
    hits = [_hit(index, text="regla " * 500) for index in range(3)]
    budget(20)
    state = {"query": "tope", "hits": hits, "supervisor_steps": 3}

    update = asyncio.run(answer_synthesizer(state, {"configurable": {"llm": RefusingLLM()}}))

    assert update["answer"] == INSUFFICIENT_CONTEXT_MESSAGE
    assert update["citations"] == []
    assert update["dropped_hits"] == 3
    assert update["context_truncated"] is True


class CapturingLLM:
    """Keeps the prompt so a test can look at it. || Guarda el prompt."""

    def __init__(self) -> None:
        self.system = ""
        self.user = ""

    def complete(self, *, system: str, user: str) -> str:
        self.system = system
        self.user = user
        return "Respuesta citada [CA014 · Validaciones]"


def _session_state(**overrides) -> dict:
    state = {
        "query": "¿y eso?",
        "resolved_question": "¿y eso? (sobre CA014)",
        "hits": [_hit(0)],
        "supervisor_steps": 3,
        "session_id": "s-1",
        "conversation_facts": {"module_code": ["CA"], "last_document_ids": ["CA014"]},
        "conversation_anchors": [],
        "conversation_turns": [
            {
                "question": "¿qué valida CA014?",
                "resolved_question": "¿qué valida CA014?",
                "answer": "valida el capital",
                "created_at": "2026-09-05T00:00:00Z",
            }
        ],
    }
    state.update(overrides)
    return state


def test_without_a_session_the_prompt_has_no_memory_block(budget):
    """Byte-identical to prompt v1, which is what keeps the eval comparable.

    || Idéntico al prompt v1, que es lo que mantiene comparable el eval.
    """
    budget(10_000)
    llm = CapturingLLM()

    asyncio.run(
        answer_synthesizer(
            {"query": "tope", "hits": [_hit(0)], "supervisor_steps": 3},
            {"configurable": {"llm": llm}},
        )
    )

    assert "Memoria de la conversación" not in llm.system


def test_with_a_session_the_memory_block_enters_the_prompt(budget):
    budget(10_000)
    llm = CapturingLLM()

    asyncio.run(answer_synthesizer(_session_state(), {"configurable": {"llm": llm}}))

    assert "Memoria de la conversación" in llm.system
    assert "¿qué valida CA014?" in llm.system


def test_the_model_is_asked_the_resolved_question(budget):
    """Answering the written question while citing evidence found for the
    resolved one is how a session produces a well-cited wrong answer.

    || Responder la escrita citando evidencia de la resuelta es como una
    sesión produce una respuesta bien citada pero equivocada.
    """
    budget(10_000)
    llm = CapturingLLM()

    asyncio.run(answer_synthesizer(_session_state(), {"configurable": {"llm": llm}}))

    assert "(sobre CA014)" in llm.user


def test_memory_never_takes_budget_from_evidence(budget):
    """The tight-budget case: memory is trimmed, every chunk still enters.

    || El caso de presupuesto ajustado: se recorta la memoria, cada chunk entra.
    """
    hits = [_hit(index, text="regla de negocio " * 40) for index in range(3)]
    fits_all = sum(
        count_tokens(render_hit_block(position, SearchHit.model_validate(hit)))
        for position, hit in enumerate(hits, start=1)
    )
    budget(fits_all)
    llm = CapturingLLM()

    update = asyncio.run(
        answer_synthesizer(
            _session_state(hits=hits), {"configurable": {"llm": llm}}
        )
    )

    assert update["dropped_hits"] == 0
    assert len(update["citations"]) == 3
    # The facts survive even with nothing left over -- they are what repairs
    # the next turn. || Los hechos sobreviven igual: son lo que arregla el
    # turno siguiente.
    assert "CA014" in llm.system


def test_no_hits_reports_zero_dropped():
    """Nothing found is not the same as nothing fitting.

    || No haber encontrado nada no es lo mismo que no haber entrado nada.
    """
    state = {"query": "algo", "hits": [], "supervisor_steps": 3}

    update = asyncio.run(answer_synthesizer(state, {"configurable": {"llm": RefusingLLM()}}))

    assert update["answer"] == INSUFFICIENT_CONTEXT_MESSAGE
    assert update["dropped_hits"] == 0
    assert update["context_truncated"] is False
