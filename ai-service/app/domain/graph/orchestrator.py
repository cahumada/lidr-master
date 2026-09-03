"""Dynamic orchestrator for the answer-orchestration graph.

The node that decides which specialist acts next. Three deterministic brakes:

* step budget (``ANSWER_ORCHESTRATOR_MAX_STEPS``)
* legality guard (inputs ready, no illegal re-runs)
* fallback ladder when routing fails

|| Orquestador dinámico del grafo de respuestas. Tres frenos deterministas.
"""

from __future__ import annotations

import structlog
from langgraph.types import Command

from app.config import get_settings
from app.domain.schemas import AnswerAgentState

log = structlog.get_logger()

_ORDER = [
    "query_planner",
    "evidence_retriever",
    "answer_synthesizer",
    "citation_validator",
]


def _already_ran(agent: str, state: AnswerAgentState) -> bool:
    """Whether ``agent`` was already dispatched on this run.

    || Si ``agent`` ya fue despachado en esta corrida.
    """
    return any(record.get("next_agent") == agent for record in (state.get("routing_history") or []))


def _inputs_ready(agent: str, state: AnswerAgentState) -> bool:
    """Whether ``agent``'s preconditions are satisfied.

    || Si se cumplen las precondiciones de ``agent``.
    """
    if agent == "query_planner":
        return bool(state.get("query"))
    if agent == "evidence_retriever":
        if state.get("requery_requested"):
            return bool(state.get("requery") or state.get("query"))
        return bool(state.get("query")) and (
            bool(state.get("sub_queries")) or _already_ran("query_planner", state)
        )
    if agent == "answer_synthesizer":
        return _already_ran("evidence_retriever", state)
    if agent == "citation_validator":
        return bool(state.get("answer"))
    return False


def _is_legal(target: str, state: AnswerAgentState) -> bool:
    """Whether routing to ``target`` is coherent with the current state.

    || Si enrutar a ``target`` es coherente con el estado actual.
    """
    if target == "finish":
        return True
    if target not in _ORDER:
        return False
    if target == "evidence_retriever" and state.get("requery_requested"):
        return _inputs_ready(target, state)
    if target == "answer_synthesizer" and state.get("pending_resynthesis"):
        return _inputs_ready(target, state)
    if target == "citation_validator" and state.get("pending_revalidation"):
        return _inputs_ready(target, state)
    return _inputs_ready(target, state) and not _already_ran(target, state)


def _fallback_next(state: AnswerAgentState) -> str:
    """Deterministic dependency ladder: first agent that can still act.

    || Escalera determinista: primer agente que todavía puede actuar.
    """
    if state.get("requery_requested") and _is_legal("evidence_retriever", state):
        return "evidence_retriever"
    for agent in _ORDER:
        if _is_legal(agent, state):
            return agent
    return "finish"


async def orchestrator(state: AnswerAgentState) -> Command:
    """Route to the next specialist via ``Command(goto=...)``.

    || Enruta al siguiente especialista vía ``Command(goto=...)``.
    """
    settings = get_settings()
    step = int(state.get("supervisor_steps") or 0)

    if step >= settings.ANSWER_ORCHESTRATOR_MAX_STEPS:
        target = "finish"
        reason = f"step budget of {settings.ANSWER_ORCHESTRATOR_MAX_STEPS} exhausted; finishing"
        source = "limit"
        log.warning("orchestrator_step_budget_exhausted", step=step)
    else:
        target = _fallback_next(state)
        reason = f"dependency ladder selected {target!r}"
        source = "fallback"

        if not _is_legal(target, state):
            overridden = target
            target = _fallback_next(state)
            reason = (
                f"proposed {overridden!r}, which is not legal; overridden to {target!r}"
            )
            source = "fallback"
            log.warning(
                "orchestrator_route_overridden",
                step=step,
                proposed=overridden,
                chosen=target,
            )

    goto = "answer_review_gate" if target == "finish" else target
    log.info(
        "orchestrator_route",
        step=step,
        next_agent=target,
        goto=goto,
        source=source,
        reason=reason[:200],
    )
    update: dict = {
        "next_agent": target,
        "route_reason": reason,
        "supervisor_steps": step + 1,
        "routing_history": [
            {
                "step": step,
                "next_agent": target,
                "reason": reason,
                "source": source,
            }
        ],
    }
    if goto == "evidence_retriever":
        update["retrieval_attempts"] = int(state.get("retrieval_attempts") or 0) + 1
    if goto not in {"evidence_retriever", "answer_synthesizer"}:
        update["requery_requested"] = False
    return Command(goto=goto, update=update)
