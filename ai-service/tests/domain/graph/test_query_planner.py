"""Query planner agent tests.

|| Tests del agente query_planner.
"""

from __future__ import annotations

import asyncio

from app.domain.graph.agents.query_planner import query_planner


def test_decompose_splits_compound_questions():
    state = {
        "query": "En PAC, ¿cómo afecta TRANSBANK, cómo afecta débito automático?",
        "supervisor_steps": 1,
    }
    update = asyncio.run(query_planner(state))
    assert len(update["sub_queries"]) >= 2


def test_naming_a_transaction_does_not_filter_by_module():
    """El test que fijaba el bug, invertido.

    Antes afirmaba `module_code == ["CA"]`, y ese filtro recortaba a un módulo
    que el corpus no tiene (`DMECAR`, `DMECLI`, …): la pregunta volvía con cero
    evidencia. La transacción la encuentra la rama de coincidencia exacta por
    `document_id`, sin filtro de módulo.
    """
    state = {"query": "¿Qué valida CA014?", "supervisor_steps": 1}
    update = asyncio.run(query_planner(state))
    assert update["filters"] == {}
    assert update["filter_sources"] == {}


# --- with a conversation session ---------------------------------------


def test_without_a_session_the_question_is_untouched():
    """The path that existed before sessions, unchanged.

    || El camino que existía antes de las sesiones, igual.
    """
    state = {"query": "¿y eso?", "supervisor_steps": 1}

    update = asyncio.run(query_planner(state))

    assert update["resolved_question"] == "¿y eso?"
    assert update["resolved_referents"] == []


def test_a_referential_question_is_resolved_before_it_is_decomposed():
    """Sub-queries derive from the RESOLVED question, or they are two
    unretrievable questions instead of one.

    || Las subconsultas salen de la pregunta RESUELTA, o son dos preguntas
    imposibles de buscar en vez de una.
    """
    state = {
        "query": "¿y para siniestros?",
        "supervisor_steps": 1,
        "conversation_facts": {"last_document_ids": ["CA014"]},
    }

    update = asyncio.run(query_planner(state))

    assert "CA014" in update["resolved_question"]
    assert update["resolved_referents"] == ["CA014"]
    assert all("CA014" in sub for sub in update["sub_queries"])


def test_the_substitution_is_audited():
    """A rewrite nobody can see is a rewrite nobody can check.

    || Una reescritura que nadie ve es una que nadie puede chequear.
    """
    state = {
        "query": "¿y eso?",
        "supervisor_steps": 1,
        "conversation_facts": {"last_document_ids": ["CA014"]},
    }

    update = asyncio.run(query_planner(state))

    assert "CA014" in update["agent_contributions"][0]["summary"]


def test_a_pinned_filter_applies_when_the_question_names_none():
    state = {
        "query": "¿cuál es el tope de capital?",
        "supervisor_steps": 1,
        "conversation_anchors": [
            {"kind": "module_code", "value": "CA", "source_question": "solo módulo CA"}
        ],
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"].get("module_code") == ["CA"]


def test_request_filter_reaches_the_resolved_filters():
    """The bug in one line: what the client asked for has to survive.

    || El bug en una línea: lo que pidió el cliente tiene que sobrevivir.
    """
    state = {
        "query": "¿Qué validaciones hay?",
        "supervisor_steps": 1,
        "request_filters": {"module_code": ["CA"]},
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"]["module_code"] == ["CA"]
    assert update["filter_sources"]["module_code"] == "request"


def test_an_anchor_applies_when_nothing_else_does():
    state = {
        "query": "¿Qué validaciones hay?",
        "supervisor_steps": 1,
        "conversation_anchors": [{"kind": "module_code", "value": "DF"}],
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"]["module_code"] == ["DF"]
    assert update["filter_sources"]["module_code"] == "anchor"


def test_a_partial_request_does_not_erase_the_other_sources():
    """Resolution is per field: a module in the body keeps an anchored type.

    || La resolución es por campo: un módulo en el body conserva el tipo fijado.
    """
    state = {
        "query": "¿Qué validaciones hay?",
        "supervisor_steps": 1,
        "request_filters": {"module_code": ["CA"]},
        "conversation_anchors": [{"kind": "window_type_name", "value": "Menu"}],
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"]["module_code"] == ["CA"]
    assert update["filters"]["window_type_name"] == ["Menu"]
    assert update["filter_sources"] == {"module_code": "request", "window_type_name": "anchor"}


def test_without_filters_nothing_is_reported():
    """The regression that matters: the no-filter path is what every eval uses.

    || La regresión que importa: el camino sin filtros es el que usan los evals.
    """
    state = {"query": "¿Qué validaciones hay?", "supervisor_steps": 1}

    update = asyncio.run(query_planner(state))

    assert update["filters"] == {}
    assert update["filter_sources"] == {}


def test_the_audit_trail_names_the_source():
    state = {
        "query": "¿Qué validaciones hay?",
        "supervisor_steps": 1,
        "request_filters": {"module_code": ["CA"]},
    }

    update = asyncio.run(query_planner(state))

    summary = update["agent_contributions"][0]["summary"]
    assert "module_code=['CA'] (request)" in summary


def test_a_pinned_prefix_reaches_the_filters():
    """«solo módulo CA» recorta por prefijo de transacción, no por module_code.

    El defecto que esto fija: como `module_code` no matcheaba nada, un anchor
    fijado en el primer turno dejaba sin evidencia todos los siguientes.
    """
    state = {
        "query": "¿Qué validaciones hay?",
        "supervisor_steps": 1,
        "conversation_anchors": [{"kind": "transaction_prefix", "value": "CA"}],
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"] == {"transaction_prefix": ["CA"]}
    assert update["filter_sources"] == {"transaction_prefix": "anchor"}


def test_the_request_still_wins_over_a_pin():
    state = {
        "query": "¿Qué validaciones hay?",
        "supervisor_steps": 1,
        "request_filters": {"module_code": ["DMECAR"]},
        "conversation_anchors": [{"kind": "module_code", "value": "DMECLI"}],
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"]["module_code"] == ["DMECAR"]
    assert update["filter_sources"]["module_code"] == "request"
