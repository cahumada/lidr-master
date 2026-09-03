"""Answer synthesis agent — reuses prompt_builder and get_answer_llm(), zero tools.

|| Agente de síntesis — reusa prompt_builder y get_answer_llm(), cero tools.
"""

from __future__ import annotations

from time import perf_counter

import structlog
from langchain_core.runnables import RunnableConfig

from app.domain.graph.privilege import record_model_action
from app.domain.schemas import AnswerAgentState
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE
from app.generation.rag.prompt_builder import build_messages
from app.generation.rag.schemas import SearchHit

log = structlog.get_logger()


async def answer_synthesizer(state: AnswerAgentState, config: RunnableConfig) -> dict:
    """Generate a cited answer from retrieved hits.

    || Genera una respuesta citada a partir de los hits recuperados.
    """
    deps = (config.get("configurable") or {}) if config else {}
    llm = deps.get("llm")
    if llm is None:
        raise RuntimeError("answer_synthesizer requires configurable.llm")

    step = int(state.get("supervisor_steps") or 0)
    query = state.get("query") or ""
    hits = [SearchHit.model_validate(hit) for hit in (state.get("hits") or [])]
    was_resynthesis = bool(state.get("pending_resynthesis"))

    if not hits:
        contribution = record_model_action(
            "answer_synthesizer",
            "insufficient_context",
            step=step,
            summary="no hits; skipped LLM",
        )
        log.info("agent_answer_synthesizer_empty", query=query)
        return {
            "answer": INSUFFICIENT_CONTEXT_MESSAGE,
            "citations": [],
            "agent_contributions": [contribution],
        }

    started = perf_counter()
    system, user = build_messages(query, hits)
    answer = llm.complete(system=system, user=user)
    contribution = record_model_action(
        "answer_synthesizer",
        "synthesize_answer",
        step=step,
        summary=f"answer over {len(hits)} hits",
        duration_ms=int((perf_counter() - started) * 1000),
    )
    log.info("agent_answer_synthesizer", hits=len(hits), answer_chars=len(answer))
    return {
        "answer": answer,
        "citations": [hit.model_dump() for hit in hits],
        "pending_resynthesis": False,
        "pending_revalidation": was_resynthesis,
        "agent_contributions": [contribution],
    }
