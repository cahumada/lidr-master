"""close_turn writes both slots: the memory window and the transcript.

No graph and no database: the store is a recorder. This is the place that
fixes "one HistoryTurn per closed run" and "the snapshot carries no chunk
text" without standing up the whole agentic path.

|| close_turn escribe los dos slots. El store es un grabador: acá se fija
un HistoryTurn por corrida cerrada y que el snapshot no carga el text.
"""

from __future__ import annotations

import asyncio

from app.domain.graph.runner import TURN_ANSWER_MAX_CHARS, close_turn
from app.generation.conversation.models import ConversationSession


class _Recorder:
    def __init__(self) -> None:
        self.saved: ConversationSession | None = None

    async def save(self, conversation: ConversationSession) -> None:
        self.saved = conversation


def _run(conversation: ConversationSession, values: dict) -> ConversationSession:
    store = _Recorder()

    async def _main() -> ConversationSession:
        await close_turn(
            store,
            conversation,
            values,
            written_question=values.get("query") or "pregunta",
            max_turns=4,
        )
        assert store.saved is not None
        return store.saved

    return asyncio.run(_main())


def test_history_keeps_the_full_answer_and_the_window_trims_it():
    long_answer = "x" * (TURN_ANSWER_MAX_CHARS + 50)
    conversation = _run(
        ConversationSession(),
        {"query": "¿CA014?", "answer": long_answer, "citations_valid": True},
    )

    assert conversation.turns[0].answer == long_answer[:TURN_ANSWER_MAX_CHARS]
    assert conversation.history[0].answer == long_answer
    assert conversation.title == "¿CA014?"


def test_a_closed_run_records_exactly_one_history_turn():
    """The gate-then-resume path calls close_turn once, at the end.

    || El camino gate-y-resume llama close_turn una vez, al cerrar.
    """
    conversation = _run(
        ConversationSession(),
        {"query": "pregunta", "answer": "aceptada", "citations_valid": True},
    )

    assert len(conversation.history) == 1
    assert conversation.history[0].answer == "aceptada"


def test_a_citation_without_document_id_is_omitted():
    conversation = _run(
        ConversationSession(),
        {
            "query": "pregunta",
            "answer": "texto",
            "citations": [
                {
                    "document_id": "CA014",
                    "document_title": "Alta",
                    "section": "Validaciones",
                    "bullet_path": "1",
                    "content_hash": "abc",
                    "text": "este texto NO viaja",
                    "score": 0.9,
                    "branches": ["vector"],
                },
                {"text": "ruido sin id", "score": 0.1},
            ],
        },
    )

    snapshots = conversation.history[0].citations
    assert [item.document_id for item in snapshots] == ["CA014"]
    dumped = snapshots[0].model_dump()
    assert dumped["content_hash"] == "abc"
    assert "text" not in dumped
    assert "score" not in dumped
