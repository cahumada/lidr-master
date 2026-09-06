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


def test_without_memory_the_prompt_is_v1():
    """An answer produced with memory is not comparable to one produced
    without it, so the version has to say which one this is.

    || Una respuesta producida con memoria no es comparable con una producida
    sin ella, así que la versión tiene que decir cuál es cuál.
    """
    system, _ = build_messages("pregunta", [_hit()])

    assert system == render_prompt("answer", "v1", "system", persona=None, guardrails=None)
    assert "Lo que ya pasó en esta conversación" not in system


def test_memory_renders_the_v2_prompt():
    system, _ = build_messages("pregunta", [_hit()], memory="- Módulos en juego: CA")

    assert "Lo que ya pasó en esta conversación" in system
    assert "- Módulos en juego: CA" in system


def test_memory_is_declared_not_to_be_provenance():
    """A remembered document_id must not look like a citable source.

    || Un document_id recordado no puede parecer una fuente citable.
    """
    system, _ = build_messages("pregunta", [_hit()], memory="- La respuesta anterior citó: CA014")

    assert "NO es procedencia" in system


def test_memory_does_not_displace_the_citation_rules():
    """Same subordination as the persona: it changes what is understood,
    never the obligation to cite.

    || La misma subordinación que la persona: cambia lo que se entiende, nunca
    la obligación de citar.
    """
    system, _ = build_messages("pregunta", [_hit()], memory="- Módulos en juego: CA")

    assert "[document_id · section]" in system
    assert system.index("Reglas, todas obligatorias") < system.index(
        "Lo que ya pasó en esta conversación"
    )


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
    assert "Fuentes citadas" in user
    assert system != user


def test_the_system_prompt_instructs_grounding_synthesis_sources_and_refusal():
    system = render_prompt("answer", "v1", "system")

    assert "SOLO" in system
    assert "No cites procedencia" in system
    assert "en el cuerpo" in system
    assert "Fuentes citadas" in system
    assert "comunicación efectiva, no un volcado" in system
    assert "No hay información suficiente" in system


def test_the_base_role_covers_both_profiles_and_is_not_a_persona():
    """Functional vs technical voice is the named profile, not the system role.

    || La voz funcional o técnica es el perfil nombrado, no el rol del system.
    """
    system = render_prompt("answer", "v1", "system")

    assert "Eres un analista funcional" not in system
    assert "el funcional" in system
    assert "el técnico" in system
    assert "ajustan la voz" in system or "ajusta la voz" in system
    assert "nunca el alcance" in system


def test_the_user_prompt_asks_for_prose_and_a_source_footer():
    _, user = build_messages("¿cuál es el tope de capital?", [_hit()])

    assert "citá con esos identificadores" not in user
    assert "Fuentes citadas" in user
    assert "no para reenviar" in user


def test_no_persona_renders_the_prompt_exactly_as_before():
    # What keeps the fidelity eval comparable across runs where nobody
    # configured a persona: the prompt has to be byte-identical.
    # || Lo que mantiene comparable el eval de fidelidad cuando nadie configuró
    # una persona: el prompt tiene que ser idéntico.
    without_argument, _ = build_messages("pregunta", [_hit()])
    with_none, _ = build_messages("pregunta", [_hit()], persona=None)

    assert without_argument == with_none
    assert "Estilo y voz" not in without_argument


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


def test_no_operator_extras_keeps_the_prompt_byte_identical():
    # Omitting guardrails must not add the extras heading — that is what
    # keeps the fidelity eval comparable when nobody configured them.
    # || Omitir guardrails no debe agregar el encabezado de extras: es lo que
    # mantiene comparable el eval de fidelidad.
    without_argument, _ = build_messages("pregunta", [_hit()])
    with_nones, _ = build_messages(
        "pregunta", [_hit()], persona=None, guardrails=None
    )

    assert without_argument == with_nones
    assert "Restricciones adicionales" not in without_argument
    assert "Estilo y voz" not in without_argument


def test_operator_guardrails_are_appended_after_the_rules_and_subordinate():
    system, _ = build_messages(
        "pregunta",
        [_hit()],
        guardrails="- Advertí que los importes dependen de la póliza.",
    )

    assert "Advertí que los importes dependen de la póliza." in system
    assert "Restricciones adicionales" in system
    assert system.index("[document_id · section]") < system.index("Advertí que los importes")
    assert "ignóralo y sigue las reglas" in system


def test_persona_comes_before_operator_guardrails():
    system, _ = build_messages(
        "pregunta",
        [_hit()],
        persona="Respondé como un analista funcional.",
        guardrails="- No recomiendes un workaround.",
    )

    assert system.index("Respondé como un analista funcional.") < system.index(
        "No recomiendes un workaround."
    )
