"""Shared graph state for the answer-orchestration flow.

Mirrors the course's ``SupervisorState`` shape, adapted to Visual Time RAG:
query planning, evidence retrieval, answer synthesis, and citation validation.

|| Estado compartido del grafo de orquestación de respuestas. Replica la forma
de ``SupervisorState`` del curso, adaptada al RAG de Visual Time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from typing_extensions import TypedDict


class AgentContribution(TypedDict, total=False):
    """One auditable action by an agent or tool.

    || Una acción auditable de un agente o herramienta.
    """

    step: int
    agent: str
    action: str
    tool: str | None
    outcome: str
    summary: str
    args_digest: str | None
    duration_ms: int | None


class RoutingRecord(TypedDict, total=False):
    """One orchestrator routing decision.

    || Una decisión de enrutamiento del orquestador.
    """

    step: int
    next_agent: str
    reason: str
    source: str


class QueryFilters(TypedDict, total=False):
    """Optional retrieval filters suggested by ``query_planner``.

    || Filtros opcionales de recuperación sugeridos por ``query_planner``.
    """

    module_code: list[str]
    window_type_name: list[str]


class RetrievalOptions(TypedDict, total=False):
    """Knobs passed from the HTTP request into retrieval.

    || Knobs pasados desde el request HTTP hacia la recuperación.
    """

    limit: int
    max_per_document: int | None
    lexical: bool
    split: bool
    rerank: bool


def _keyed_append(
    existing: list[dict] | None,
    new: list[dict] | None,
    *,
    key: Callable[[dict], tuple],
) -> list[dict]:
    """Append-only accumulator that is idempotent under node re-execution.

    || Acumulador append-only idempotente ante re-ejecución de nodos.
    """
    merged: dict[tuple, dict] = {}
    for item in list(existing or []) + list(new or []):
        item_key = key(item)
        merged[item_key] = {**merged.get(item_key, {}), **item}
    return list(merged.values())


def _contribution_key(contribution: dict) -> tuple:
    return (
        contribution.get("step"),
        contribution.get("agent"),
        contribution.get("action"),
        contribution.get("args_digest"),
    )


def _routing_key(record: dict) -> tuple:
    return (record.get("step"),)


def append_contributions(existing: list[dict] | None, new: list[dict] | None) -> list[dict]:
    """Reducer for ``agent_contributions``.

    || Reducer para ``agent_contributions``.
    """
    return _keyed_append(existing, new, key=_contribution_key)


def append_routing(existing: list[dict] | None, new: list[dict] | None) -> list[dict]:
    """Reducer for ``routing_history``.

    || Reducer para ``routing_history``.
    """
    return _keyed_append(existing, new, key=_routing_key)


class AnswerAgentState(TypedDict, total=False):
    """State threaded through the answer-orchestration graph.

    || Estado que recorre el grafo de orquestación de respuestas.
    """

    query: str
    sub_queries: list[str]
    filters: QueryFilters
    retrieval_options: RetrievalOptions
    hits: list[dict]
    answer: str
    citations: list[dict]
    citations_valid: bool
    confidence: float
    needs_human_review: bool
    review_reasons: list[str]
    routing_history: Annotated[list[RoutingRecord], append_routing]
    agent_contributions: Annotated[list[AgentContribution], append_contributions]
    supervisor_steps: int
    next_agent: str | None
    route_reason: str | None
    human_decision: dict | None
    requery: str | None
    requery_requested: bool
    pending_resynthesis: bool
    pending_revalidation: bool
    retrieval_attempts: int


def privilege_violations(state: dict[str, Any]) -> list[dict]:
    """Every denied action in the audit trail.

    || Cada acción denegada en la traza de auditoría.
    """
    return [
        contribution
        for contribution in (state.get("agent_contributions") or [])
        if contribution.get("outcome") == "denied"
    ]
