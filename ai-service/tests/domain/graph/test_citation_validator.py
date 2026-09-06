"""Citation validator agent tests.

|| Tests del agente citation_validator.
"""

from __future__ import annotations

import asyncio

from app.domain.graph.agents.citation_validator import citation_validator


def test_grounded_answer_is_valid():
    state = {
        "query": "q",
        "answer": "Según [CA014 · Validaciones] el tope aplica.",
        "citations": [
            {
                "content_hash": "h1",
                "chunk_id": "c1",
                "document_id": "CA014",
                "document_title": "t",
                "section": "Validaciones",
                "text": "texto",
                "score": 0.1,
            }
        ],
        "retrieval_attempts": 1,
        "supervisor_steps": 4,
    }
    update = asyncio.run(citation_validator(state))
    assert update["citations_valid"] is True
    assert update["confidence"] >= 0.7


def test_ungrounded_answer_requests_requery():
    state = {
        "query": "q",
        "answer": "Según [ZZ999 · Función] aplica.",
        "citations": [
            {
                "content_hash": "h1",
                "chunk_id": "c1",
                "document_id": "CA014",
                "document_title": "t",
                "section": "Validaciones",
                "text": "texto",
                "score": 0.1,
            }
        ],
        "retrieval_attempts": 1,
        "supervisor_steps": 4,
    }
    update = asyncio.run(citation_validator(state))
    assert update["citations_valid"] is False
    assert update["requery_requested"] is True
    assert "ZZ999" in (update.get("requery") or "")


def test_memory_is_never_provenance():
    """A document_id from an earlier turn does not back this answer.

    The session can carry `CO001` in its facts and in the memory block, and
    the model can read it there -- none of that makes it a citable source for
    the CURRENT turn. The validator only ever looks at this turn's hits.

    || Un document_id de un turno anterior no respalda esta respuesta. La
    sesión puede llevar `CO001` en sus hechos y en el bloque de memoria, y el
    modelo puede leerlo ahí: nada de eso lo convierte en una fuente citable
    del turno ACTUAL. El validador solo mira los hits de este turno.
    """
    state = {
        "query": "q",
        "resolved_question": "q (sobre CO001)",
        "answer": "Según [CO001 · Función] aplica.",
        "citations": [
            {
                "content_hash": "h1",
                "chunk_id": "c1",
                "document_id": "CA014",
                "document_title": "t",
                "section": "Validaciones",
                "text": "texto",
                "score": 0.1,
            }
        ],
        # The session remembers CO001 from the previous turn.
        # || La sesión recuerda CO001 del turno anterior.
        "session_id": "s-1",
        "conversation_facts": {"last_document_ids": ["CO001"]},
        "retrieval_attempts": 1,
        "supervisor_steps": 4,
    }

    update = asyncio.run(citation_validator(state))

    assert update["citations_valid"] is False
