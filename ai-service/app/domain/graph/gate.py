"""Human-in-the-loop gate for agentic answers.

Pauses only when ``review_reasons(state)`` is non-empty — a gate that always
fires is a form, not a control.

|| Gate human-in-the-loop para respuestas agenticas. Pausa solo cuando
``review_reasons(state)`` no está vacío.
"""

from __future__ import annotations

import structlog
from langgraph.types import interrupt

from app.config import Settings, get_settings
from app.domain.schemas import AnswerAgentState
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE

log = structlog.get_logger()


def review_reasons(state: AnswerAgentState, settings: Settings | None = None) -> list[str]:
    """Trigger conditions that currently hold. Empty list means ship it.

    Pure function of state: ``interrupt()`` re-executes this node on resume, so
    the pause branch must be deterministic.

    || Condiciones de disparo que aplican ahora. Lista vacía = entregar. Función
    pura del estado: ``interrupt()`` re-ejecuta este nodo al resumir.
    """
    settings = settings or get_settings()
    reasons: list[str] = []

    confidence = state.get("confidence")
    if confidence is not None and confidence < settings.ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD:
        reasons.append(
            f"confidence {confidence:.2f} is below the "
            f"{settings.ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD:.2f} threshold"
        )

    if state.get("citations_valid") is False:
        reasons.append("the answer cites document_ids that are not among the retrieved hits")

    hits = state.get("hits") or []
    answer = state.get("answer") or ""
    if not hits and answer == INSUFFICIENT_CONTEXT_MESSAGE:
        reasons.append("no evidence was retrieved for this question in the loaded corpus")

    if state.get("needs_human_review"):
        for reason in state.get("review_reasons") or []:
            if reason not in reasons:
                reasons.append(reason)

    return reasons


def needs_human_review(state: AnswerAgentState, settings: Settings | None = None) -> bool:
    """Whether this answer must stop for a person.

    || Si esta respuesta debe detenerse para una persona.
    """
    return bool(review_reasons(state, settings))


def _apply_decision(state: AnswerAgentState, decision: dict) -> tuple[str, bool]:
    """Apply the human decision. Returns ``(status, citations_valid)``."""
    action = (decision or {}).get("decision") or (decision or {}).get("action") or "approve"
    if action == "reject":
        return "rejected", state.get("citations_valid", False)
    return "approved", state.get("citations_valid", True)


async def answer_review_gate(state: AnswerAgentState) -> dict:
    """Pause for human review when triggers fire; otherwise fall through.

    || Pausa para revisión humana cuando disparan los triggers; si no, sigue.
    """
    reasons = review_reasons(state)

    if not reasons:
        log.info(
            "answer_review_gate_skipped",
            confidence=state.get("confidence"),
            citations_valid=state.get("citations_valid"),
        )
        return {"needs_human_review": False, "review_reasons": []}

    decision = interrupt(
        {
            "gate": "answer_review",
            "query": state.get("query"),
            "reasons": reasons,
            "confidence": state.get("confidence"),
            "threshold": get_settings().ANSWER_ORCHESTRATOR_CONFIDENCE_THRESHOLD,
            "answer": state.get("answer"),
            "citations": state.get("citations") or [],
            "routing_history": state.get("routing_history") or [],
        }
    )

    decision = decision or {}
    status, citations_valid = _apply_decision(state, decision)
    action = decision.get("decision") or decision.get("action") or "approve"
    log.info(
        "answer_review_gate_resumed",
        action=action,
        status=status,
        reasons=len(reasons),
    )
    return {
        "status": status,
        "human_decision": decision,
        "needs_human_review": True,
        "review_reasons": reasons,
        "citations_valid": citations_valid,
        "agent_contributions": [
            {
                "step": int(state.get("supervisor_steps") or 0),
                "agent": "human",
                "action": "review_decision",
                "tool": None,
                "outcome": "ok",
                "summary": f"human {action}: {decision.get('note') or '—'}",
                "args_digest": None,
                "duration_ms": None,
            }
        ],
    }
