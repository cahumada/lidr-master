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
