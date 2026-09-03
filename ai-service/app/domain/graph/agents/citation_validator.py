"""Citation validation agent — formal guardrail check, zero tools.

Can approve, request one requery to ``evidence_retriever``, or flag human review.

|| Agente de validación de citas — chequeo formal del guardrail, cero tools.
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.domain.graph.privilege import record_model_action
from app.domain.schemas import AnswerAgentState
from app.generation.rag.guardrails import check_grounding
from app.generation.rag.schemas import SearchHit

log = structlog.get_logger()


def _confidence_score(*, grounded: bool, hit_count: int) -> float:
    """Map grounding and evidence volume to a 0..1 confidence signal.

    || Mapea grounding y volumen de evidencia a una señal de confianza 0..1.
    """
    if hit_count == 0:
        return 0.1
    if grounded and hit_count >= 3:
        return 0.9
    if grounded:
        return 0.75
    return 0.35


async def citation_validator(state: AnswerAgentState) -> dict:
    """Run the output guardrail and publish facts for the gate.

    || Corre el guardrail de salida y publica hechos para el gate.
    """
    settings = get_settings()
    step = int(state.get("supervisor_steps") or 0)
    answer = state.get("answer") or ""
    hits = [SearchHit.model_validate(hit) for hit in (state.get("citations") or state.get("hits") or [])]
    grounding = check_grounding(answer, hits)
    hit_count = len(hits)
    confidence = _confidence_score(grounded=grounding.grounded, hit_count=hit_count)

    update: dict = {
        "citations_valid": grounding.grounded,
        "confidence": confidence,
        "pending_revalidation": False,
        "agent_contributions": [
            record_model_action(
                "citation_validator",
                "validate_citations",
                step=step,
                summary=(
                    f"grounded={grounding.grounded}; unsupported="
                    f"{grounding.unsupported_document_ids}"
                ),
            )
        ],
    }

    retrieval_attempts = int(state.get("retrieval_attempts") or 0)
    if (
        not grounding.grounded
        and retrieval_attempts <= settings.ANSWER_ORCHESTRATOR_MAX_REQUERIES
        and hit_count > 0
    ):
        unsupported = grounding.unsupported_document_ids
        refined = f"{state.get('query') or ''} {' '.join(unsupported)}".strip()
        update["requery"] = refined
        update["requery_requested"] = True
        log.info("agent_citation_validator_requery", refined=refined[:120])
    elif not grounding.grounded or hit_count == 0:
        update["needs_human_review"] = True
        update["review_reasons"] = [
            "citation validation failed or no corpus evidence was found"
        ]

    log.info(
        "agent_citation_validator",
        grounded=grounding.grounded,
        confidence=confidence,
        hits=hit_count,
    )
    return update
