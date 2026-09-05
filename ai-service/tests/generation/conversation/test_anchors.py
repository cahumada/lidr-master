"""A mention is not a pin. || Una mención no es un anchor.

The detector is conservative on purpose: a miss leaves the turn in the
ordinary window, a false positive silently narrows every later search.

|| El detector es conservador a propósito: un falso negativo deja el turno en
la ventana común, un falso positivo acota en silencio todo lo que sigue.
"""

from __future__ import annotations

import pytest

from app.generation.conversation.anchors import detect_anchors


@pytest.mark.parametrize(
    "question",
    [
        "de acá en adelante, solo módulo CA",
        "de ahora en más quedate en el módulo CA",
        "para todo lo que sigue, módulo CA",
        "siempre módulo CA",
        "solo módulo CA por favor",
    ],
)
def test_a_scoping_phrase_with_a_module_pins_it(question):
    anchors = detect_anchors(question)

    assert [(a.kind, a.value) for a in anchors] == [("module_code", "CA")]


def test_the_pinning_question_is_recorded():
    """A filter with no visible origin is indistinguishable from a bug.

    || Un filtro sin origen visible no se distingue de un bug.
    """
    question = "de acá en adelante, solo módulo CA"

    assert detect_anchors(question)[0].source_question == question


@pytest.mark.parametrize(
    "question",
    [
        "¿qué valida el módulo CA?",
        "mostrame las transacciones del módulo CA",
        "en el módulo CA, ¿cuál es el tope?",
    ],
)
def test_merely_naming_a_module_pins_nothing(question):
    """That is a filter for one question, not a decision about the conversation.

    || Eso es un filtro de una pregunta, no una decisión sobre la conversación.
    """
    assert detect_anchors(question) == []


def test_a_scoping_phrase_with_nothing_to_pin_yields_nothing():
    """"Sé más breve" scopes nothing the retriever can use.

    || «Sé más breve» no acota nada que el retriever pueda usar.
    """
    assert detect_anchors("de acá en adelante sé más breve") == []


def test_an_empty_question_pins_nothing():
    assert detect_anchors("") == []


def test_a_window_type_can_be_pinned():
    anchors = detect_anchors("de acá en adelante, solo ventanas de tipo Consulta.")

    assert [(a.kind, a.value) for a in anchors] == [("window_type_name", "Consulta")]
