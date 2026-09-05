"""The resolver names a referent or leaves the question alone. Never a third thing.

|| El resolver nombra un referente o deja la pregunta como está. Nunca una tercera cosa.
"""

from __future__ import annotations

import pytest

from app.generation.conversation.models import ConversationFacts
from app.generation.conversation.resolver import resolve


def test_a_referential_follow_up_becomes_retrievable():
    """The point of the whole change. || El punto de todo el cambio."""
    facts = ConversationFacts(module_code=["CA"], last_document_ids=["CA014"])

    resolved = resolve("¿y para siniestros?", facts)

    assert resolved.rewritten is True
    assert "CA014" in resolved.text
    assert resolved.substituted == ["CA014"]


def test_a_question_that_names_its_own_subject_is_untouched():
    """Rewriting it would invent a second subject.

    || Reescribirla sería inventarle un segundo sujeto.
    """
    facts = ConversationFacts(last_document_ids=["CO001"])

    resolved = resolve("¿qué valida CA014?", facts)

    assert resolved.text == "¿qué valida CA014?"
    assert resolved.rewritten is False


def test_no_referent_in_the_facts_means_no_rewrite():
    """It never invents one. || Nunca inventa uno."""
    resolved = resolve("¿y eso?", ConversationFacts(module_code=["CA"]))

    assert resolved.text == "¿y eso?"
    assert resolved.substituted == []


def test_a_question_with_no_referential_marker_is_untouched():
    facts = ConversationFacts(last_document_ids=["CA014"])

    resolved = resolve("¿cuál es el tope de capital asegurado?", facts)

    assert resolved.rewritten is False


def test_no_session_means_no_rewrite():
    """Byte-identical to the path that existed before sessions.

    || Idéntico al camino que existía antes de las sesiones.
    """
    resolved = resolve("¿y eso?", None)

    assert resolved.text == "¿y eso?"
    assert resolved.rewritten is False


def test_the_rewrite_names_at_most_two_referents():
    """The whole citation list would bury the question itself.

    || La lista entera de citas taparía la pregunta misma.
    """
    facts = ConversationFacts(last_document_ids=["CA014", "CO001", "DF002", "PP010"])

    resolved = resolve("¿y eso?", facts)

    assert resolved.substituted == ["CA014", "CO001"]
    assert "DF002" not in resolved.text


def test_the_last_citation_wins_over_a_merely_mentioned_code():
    """It is what the user was reading when they wrote this.

    || Es lo que el usuario estaba leyendo cuando escribió esto.
    """
    facts = ConversationFacts(
        transaction_codes=["DF002"], last_document_ids=["CA014"]
    )

    assert resolve("¿y eso?", facts).substituted == ["CA014"]


def test_mentioned_codes_are_the_fallback():
    facts = ConversationFacts(transaction_codes=["DF002"])

    assert resolve("¿y eso?", facts).substituted == ["DF002"]


@pytest.mark.parametrize(
    "question",
    [
        "¿cómo se originan esos boletines en el sistema?",
        "¿cómo se reprocesa esa cobranza en el listado?",
        "¿qué controles existen si necesito traspasar ese pago a otro recibo?",
        "¿la misma cobranza se puede repetir?",
    ],
)
def test_a_demonstrative_modifying_a_noun_is_not_a_reference(question):
    """"esos boletines" names its own subject; "¿y esos?" does not.

    Measured, not assumed: an earlier version matched the demonstrative
    anywhere and rewrote 3 of the 35 golden questions, appending a referent to
    questions that already had one.

    || «esos boletines» nombra su propio sujeto; «¿y esos?» no. Medido y no
    supuesto: una versión anterior reescribía 3 de las 35 preguntas del golden
    set, agregando un referente a preguntas que ya lo tenían.
    """
    facts = ConversationFacts(last_document_ids=["ZZ999"])

    assert resolve(question, facts).rewritten is False


@pytest.mark.parametrize(
    "question",
    ["¿y esa?", "¿qué valida ese?", "contame más sobre eso", "¿y la misma?"],
)
def test_a_bare_demonstrative_is_a_reference(question):
    """Nothing follows it, so it stands in for what was said before.

    || No lo sigue nada, así que está en lugar de lo que se dijo antes.
    """
    facts = ConversationFacts(last_document_ids=["ZZ999"])

    assert resolve(question, facts).rewritten is True


def test_an_empty_question_is_not_rewritten():
    assert resolve("", ConversationFacts(last_document_ids=["CA014"])).text == ""
