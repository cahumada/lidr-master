"""What a session keeps, and what it is allowed to forget.

|| Qué conserva una sesión, y qué tiene permitido olvidar.
"""

from __future__ import annotations

from app.generation.conversation.models import (
    Anchor,
    ConversationFacts,
    ConversationSession,
    Turn,
)


def _turn(index: int) -> Turn:
    return Turn(
        question=f"pregunta {index}",
        resolved_question=f"pregunta {index}",
        answer=f"respuesta {index}",
    )


def _anchor(value: str = "CA") -> Anchor:
    return Anchor(kind="module_code", value=value, source_question="de acá en adelante, módulo CA")


# --- facts -------------------------------------------------------------


def test_lists_accumulate_across_turns():
    """Naming a second module does not un-name the first.

    || Nombrar un segundo módulo no des-nombra el primero.
    """
    first = ConversationFacts(module_code=["CA"], transaction_codes=["CA014"])
    second = ConversationFacts(module_code=["DF"], transaction_codes=["DF002"])

    merged = first.merge_with(second)

    assert merged.module_code == ["CA", "DF"]
    assert merged.transaction_codes == ["CA014", "DF002"]


def test_the_union_is_case_insensitive_and_keeps_first_seen_order():
    merged = ConversationFacts(module_code=["CA"]).merge_with(
        ConversationFacts(module_code=["ca", "DF"])
    )

    assert merged.module_code == ["CA", "DF"]


def test_the_last_citation_is_replaced_not_accumulated():
    """"What the previous answer cited" stops being true if it accumulates.

    || «Lo que citó la respuesta anterior» deja de ser cierto si acumula.
    """
    first = ConversationFacts(last_document_ids=["CA014"])
    second = ConversationFacts(last_document_ids=["CO001"])

    assert first.merge_with(second).last_document_ids == ["CO001"]


def test_a_turn_that_cited_nothing_does_not_erase_the_referent():
    """The next question may still need it. || La pregunta siguiente puede necesitarlo."""
    first = ConversationFacts(last_document_ids=["CA014"])

    assert first.merge_with(ConversationFacts()).last_document_ids == ["CA014"]


def test_empty_facts_are_empty():
    assert ConversationFacts().is_empty()
    assert not ConversationFacts(module_code=["CA"]).is_empty()


# --- the sliding window ------------------------------------------------


def test_the_window_trims_to_max_turns():
    session = ConversationSession()

    for index in range(6):
        session.append_turn(_turn(index), max_turns=4)

    assert len(session.turns) == 4
    assert [turn.question for turn in session.turns] == [
        "pregunta 2",
        "pregunta 3",
        "pregunta 4",
        "pregunta 5",
    ]


def test_the_window_drops_the_oldest_first():
    """A follow-up leans on the LAST exchange. || Un seguimiento se apoya en el ÚLTIMO."""
    session = ConversationSession()
    for index in range(3):
        session.append_turn(_turn(index), max_turns=2)

    assert session.turns[-1].question == "pregunta 2"


# --- anchors -----------------------------------------------------------


def test_anchors_survive_the_window():
    """The window never evicts a pinned constraint.

    || La ventana nunca desaloja una restricción fijada.
    """
    session = ConversationSession()
    session.pin([_anchor()])
    for index in range(10):
        session.append_turn(_turn(index), max_turns=2)

    assert len(session.anchors) == 1
    assert session.anchors[0].value == "CA"


def test_pinning_the_same_constraint_twice_adds_one():
    session = ConversationSession()
    session.pin([_anchor()])
    added = session.pin([_anchor("ca")])

    assert added == []
    assert len(session.anchors) == 1


def test_an_anchor_can_be_removed():
    session = ConversationSession()
    session.pin([_anchor()])

    assert session.unpin("module_code", "ca") is True
    assert session.anchors == []


def test_removing_an_anchor_that_is_not_there_says_so():
    assert ConversationSession().unpin("module_code", "CA") is False


def test_anchors_become_retrieval_filters():
    session = ConversationSession()
    session.pin([_anchor("CA"), _anchor("DF")])

    assert session.anchored_filters() == {"module_code": ["CA", "DF"]}
