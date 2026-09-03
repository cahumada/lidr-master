"""Orchestrator routing: legality, fallback, step budget.

|| Enrutamiento del orquestador: legalidad, fallback, tope de pasos.
"""

from __future__ import annotations

import asyncio

from langgraph.types import Command

from app.domain.graph.orchestrator import _fallback_next, _is_legal, orchestrator
from app.domain.schemas import AnswerAgentState


def test_fallback_ladder_starts_at_query_planner():
    state: AnswerAgentState = {"query": "¿Cómo funciona CA014?"}
    assert _fallback_next(state) == "query_planner"


def test_illegal_revisit_is_blocked():
    state: AnswerAgentState = {
        "query": "test",
        "sub_queries": ["test"],
        "routing_history": [{"step": 0, "next_agent": "query_planner", "reason": "", "source": "fallback"}],
    }
    assert _is_legal("query_planner", state) is False


def test_requery_allows_evidence_retriever():
    state: AnswerAgentState = {
        "query": "test",
        "requery_requested": True,
        "requery": "CA014 validaciones",
        "routing_history": [{"step": 3, "next_agent": "evidence_retriever", "reason": "", "source": "fallback"}],
    }
    assert _is_legal("evidence_retriever", state) is True


def test_step_budget_routes_to_review_gate(monkeypatch):
    monkeypatch.setattr(
        "app.domain.graph.orchestrator.get_settings",
        lambda: type("S", (), {"ANSWER_ORCHESTRATOR_MAX_STEPS": 1})(),
    )
    state: AnswerAgentState = {"query": "test", "supervisor_steps": 1}
    command = asyncio.run(orchestrator(state))
    assert isinstance(command, Command)
    assert command.goto == "answer_review_gate"
    assert command.update["next_agent"] == "finish"
