"""Memory is trimmed before evidence is, and the facts are never trimmed at all.

|| La memoria se recorta antes que la evidencia, y los hechos no se recortan nunca.
"""

from __future__ import annotations

from app.generation.conversation.budget import render_memory
from app.generation.conversation.models import (
    Anchor,
    ConversationFacts,
    ConversationSession,
    Turn,
)


def _session(*, turns: int = 0, anchors: int = 0, facts: bool = True) -> ConversationSession:
    session = ConversationSession(
        facts=ConversationFacts(
            module_code=["CA"], last_document_ids=["CA014"]
        )
        if facts
        else ConversationFacts()
    )
    session.anchors = [
        Anchor(kind="transaction_prefix", value=f"M{index}", source_question="solo módulo")
        for index in range(anchors)
    ]
    session.turns = [
        Turn(
            question=f"pregunta {index}",
            resolved_question=f"pregunta {index}",
            answer="una respuesta bastante larga sobre reglas de negocio " * 6,
        )
        for index in range(turns)
    ]
    return session


def test_no_session_renders_nothing():
    """So the no-session path stays byte-identical to prompt v1.

    || Así el camino sin sesión queda idéntico al prompt v1.
    """
    assert render_memory(None, budget=1000) is None


def test_an_empty_session_renders_nothing():
    assert render_memory(_session(facts=False), budget=1000) is None


def test_a_generous_budget_keeps_everything():
    session = _session(turns=3, anchors=1)

    block = render_memory(session, budget=10_000)

    assert block is not None
    assert block.turns_included == 3
    assert block.anchors_included == 1
    assert block.trimmed is False


def test_turns_are_dropped_before_anchors():
    """A pinned filter changes what is retrieved; a turn only repeats a sentence.

    || Un filtro fijado cambia lo que se recupera; un turno solo repite una frase.
    """
    session = _session(turns=4, anchors=1)

    block = render_memory(session, budget=120)

    assert block is not None
    assert block.turns_dropped > 0
    assert block.anchors_included == 1


def test_the_oldest_turn_goes_first():
    session = _session(turns=3)

    block = render_memory(session, budget=140)

    assert block is not None
    assert "pregunta 0" not in block.text
    assert "pregunta 2" in block.text


def test_the_facts_are_never_dropped():
    """They are what repairs the NEXT turn's retrieval.

    || Son lo que arregla la recuperación del turno SIGUIENTE.
    """
    session = _session(turns=4, anchors=2)

    block = render_memory(session, budget=1)

    assert block is not None
    assert "CA014" in block.text
    assert block.turns_included == 0
    assert block.anchors_included == 0


def test_the_block_says_it_is_not_provenance():
    """The prompt must not let a remembered id look like a citable source.

    || El prompt no puede dejar que un id recordado parezca una fuente citable.
    """
    block = render_memory(_session(turns=1), budget=10_000)

    assert block is not None
    assert "NUNCA procedencia" in block.text
