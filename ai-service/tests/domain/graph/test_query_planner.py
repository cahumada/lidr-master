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


def test_transaction_code_suggests_module_filter():
    state = {"query": "¿Qué valida CA014?", "supervisor_steps": 1}
    update = asyncio.run(query_planner(state))
    assert update["filters"].get("module_code") == ["CA"]


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


def test_the_question_wins_over_a_pinned_filter():
    """An anchor is a default, not a cage. || Un anchor es un default, no una jaula."""
    state = {
        "query": "¿qué valida DF002?",
        "supervisor_steps": 1,
        "conversation_anchors": [
            {"kind": "module_code", "value": "CA", "source_question": "solo módulo CA"}
        ],
    }

    update = asyncio.run(query_planner(state))

    assert update["filters"].get("module_code") == ["DF"]
