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
    # What a person means by "módulo CA": transactions whose code starts with
    # that prefix. A separate dimension from `module_code` on purpose — see
    # `SearchFilters.transaction_prefix`.
    # || Lo que una persona quiere decir con «módulo CA»: transacciones cuyo
    # código empieza con ese prefijo. Dimensión aparte de `module_code` a
    # propósito.
    transaction_prefix: list[str]


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
    # What the user wrote stays in `query`; `resolved_question` is what is
    # actually retrieved. Two fields and not one: a rewrite the user cannot
    # see is a rewrite nobody can check.
    # || Lo que escribió el usuario queda en `query`; `resolved_question` es lo
    # que realmente se busca. Dos campos y no uno: una reescritura que el
    # usuario no ve es una reescritura que nadie puede chequear.
    resolved_question: str
    resolved_referents: list[str]
    session_id: str | None

    # Which mirror run this turn resolves window status from. Carried as a
    # STRING and not as the tree itself: this state is serialized into the
    # LangGraph checkpointer, and a few MB of navigation tree does not belong
    # in a checkpoint. The tree comes from a process cache keyed by exactly
    # these two values, so a paused run resumed after an activation still
    # answers with the run it started on -- which is the correct behaviour: a
    # turn should not change its mind about the world halfway through.
    # || De qué corrida del mirror resuelve el estado de ventana este turno.
    # Viaja como STRING y no como el árbol: este estado se serializa al
    # checkpointer, y unos MB de árbol no van ahí. El árbol sale de un caché de
    # proceso con esas dos claves, así que una corrida pausada y retomada
    # después de una activación sigue respondiendo con la corrida en la que
    # empezó — que es lo correcto: un turno no debería cambiar de idea sobre el
    # mundo a mitad de camino.
    active_run_id: str | None
    active_run_env: str

    conversation_facts: dict
    conversation_anchors: list[dict]
    conversation_turns: list[dict]
    sub_queries: list[str]
    # What the CLIENT asked to narrow by, before any resolution. Separate from
    # `filters` on purpose: `filters` is the resolved outcome of three sources
    # and only the planner writes it, so keeping the request's own values apart
    # is what lets the precedence be decided in one place and audited.
    # || Por qué pidió recortar EL CLIENTE, antes de resolver nada. Separado de
    # `filters` a propósito: `filters` es el resultado resuelto de tres fuentes
    # y solo lo escribe el planner, así que mantener aparte lo que vino del
    # request es lo que permite decidir la precedencia en un solo lugar y
    # auditarla.
    request_filters: QueryFilters
    filters: QueryFilters
    # Which source each effective filter came from: `request`, `question` or
    # `anchor`. A filter applied without saying so is a defect, and with three
    # possible sources knowing THAT it was filtered is not enough.
    # || De qué fuente salió cada filtro efectivo. Un filtro aplicado sin
    # decirlo es un defecto, y con tres fuentes posibles saber QUE se filtró no
    # alcanza.
    filter_sources: dict[str, str]
    retrieval_options: RetrievalOptions
    hits: list[dict]
    answer: str
    citations: list[dict]
    context_truncated: bool
    dropped_hits: int
    answer_truncated: bool
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
    usage: dict
    # Id of the prompt as it went to the model, stored by the synthesizer. The
    # TEXT never enters the state: it is ~60 KB and the state is checkpointed.
    # || Id del prompt tal como salió al modelo. El TEXTO nunca entra al estado:
    # son ~60 KB y el estado se checkpointea.
    prompt_id: str | None
    business_db: dict | None


def privilege_violations(state: dict[str, Any]) -> list[dict]:
    """Every denied action in the audit trail.

    || Cada acción denegada en la traza de auditoría.
    """
    return [
        contribution
        for contribution in (state.get("agent_contributions") or [])
        if contribution.get("outcome") == "denied"
    ]
