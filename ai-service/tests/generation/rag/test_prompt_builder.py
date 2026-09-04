"""The prompt carries provenance, not bare text.

|| El prompt lleva procedencia, no texto pelado.
"""

from __future__ import annotations

from app.foundation.prompts import render_prompt
from app.generation.rag.prompt_builder import build_context, build_messages
from app.generation.rag.schemas import SearchHit


def _hit(**overrides) -> SearchHit:
    defaults = {
        "content_hash": "h1",
        "chunk_id": "CA014::Validaciones::0",
        "document_id": "CA014",
        "document_title": "Coberturas de la poliza individual",
        "section": "Validaciones",
        "bullet_path": "Capital > Limites",
        "module_code": "CA",
        "document_kind": "content",
        "text": "El capital asegurado no puede superar el maximo del plan.",
        "score": 0.031,
        "branches": ["vector"],
        "ranks": {"vector": 1},
    }
    defaults.update(overrides)
    return SearchHit(**defaults)


def test_each_chunk_enters_with_its_provenance():
    context = build_context([_hit()])

    assert "[CA014 · Validaciones]" in context
    assert "Coberturas de la poliza individual" in context
    assert "Capital > Limites" in context
    assert "El capital asegurado no puede superar el maximo del plan." in context


def test_a_missing_section_is_marked_not_guessed():
    context = build_context([_hit(section=None)])

    assert "[CA014 · (sin sección)]" in context


def test_several_hits_are_numbered_in_order():
    context = build_context(
        [
            _hit(document_id="CA014", section="Validaciones"),
            _hit(
                content_hash="h2",
                chunk_id="COL005::Función::0",
                document_id="COL005",
                section="Función",
                text="Cuadre de cobranzas.",
            ),
        ]
    )

    assert context.index("### 1.") < context.index("### 2.")
    assert "[COL005 · Función]" in context


def test_the_user_prompt_carries_the_question_and_the_context():
    system, user = build_messages("¿cuál es el tope de capital?", [_hit()])

    assert "¿cuál es el tope de capital?" in user
    assert "[CA014 · Validaciones]" in user
    assert "El capital asegurado" in user
    assert system != user


def test_the_system_prompt_instructs_grounding_citations_and_refusal():
    system = render_prompt("answer", "v1", "system")

    assert "[document_id · section]" in system
    assert "SOLO" in system
    assert "No hay información suficiente" in system


def test_no_persona_renders_the_prompt_exactly_as_before():
    # What keeps the fidelity eval comparable across runs where nobody
    # configured a persona: the prompt has to be byte-identical.
    # || Lo que mantiene comparable el eval de fidelidad cuando nadie configuró
    # una persona: el prompt tiene que ser idéntico.
    without_argument, _ = build_messages("pregunta", [_hit()])
    with_none, _ = build_messages("pregunta", [_hit()], persona=None)

    assert without_argument == with_none
    assert "perfil de agente" not in without_argument


def test_a_persona_is_appended_after_the_rules_and_subordinate_to_them():
    system, _ = build_messages(
        "pregunta", [_hit()], persona="Respondé como un analista funcional."
    )

    assert "Respondé como un analista funcional." in system
    # The rules still come first, and the persona block says outright that it
    # cannot override them — a persona is for the voice, not for opting out of
    # citing sources.
    # || Las reglas siguen primero, y el bloque de persona dice explícitamente
    # que no puede sobreescribirlas.
    assert system.index("[document_id · section]") < system.index("Respondé como")
    assert "ignóralo y sigue las reglas" in system
