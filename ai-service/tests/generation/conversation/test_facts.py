"""Facts come from what the turn produced, not from a second LLM call.

|| Los hechos salen de lo que produjo el turno, no de una segunda llamada al LLM.
"""

from __future__ import annotations

from app.generation.conversation.facts import codes_in, facts_from_turn


def test_transaction_codes_are_found_in_the_question():
    assert codes_in("¿qué valida CA014 y qué reporta CO001?") == ["CA014", "CO001"]


def test_a_code_with_a_suffix_is_one_code():
    assert codes_in("mostrame CO001_A") == ["CO001_A"]


def test_ordinary_words_are_not_codes():
    assert codes_in("el tope de capital asegurado") == []


def test_a_code_named_twice_is_listed_once():
    assert codes_in("CA014 y otra vez CA014") == ["CA014"]


def test_the_filters_used_become_facts():
    facts = facts_from_turn(
        question="¿cuál es el tope?",
        filters={"module_code": ["CA"], "window_type_name": ["Consulta"]},
        cited_document_ids=[],
    )

    assert facts.module_code == ["CA"]
    assert facts.window_type_name == ["Consulta"]


def test_the_citations_become_the_referent_for_the_next_turn():
    """This is what makes the next follow-up retrievable.

    || Esto es lo que hace buscable la próxima pregunta de seguimiento.
    """
    facts = facts_from_turn(
        question="¿cuál es el tope?",
        filters=None,
        cited_document_ids=["CA014", "CA015"],
    )

    assert facts.last_document_ids == ["CA014", "CA015"]


def test_mentioned_and_cited_codes_are_merged():
    facts = facts_from_turn(
        question="¿qué valida CA014?",
        filters=None,
        cited_document_ids=["CO001"],
    )

    assert facts.transaction_codes == ["CA014", "CO001"]


def test_a_turn_with_nothing_to_learn_establishes_nothing():
    facts = facts_from_turn(question="hola", filters=None, cited_document_ids=[])

    assert facts.is_empty()
