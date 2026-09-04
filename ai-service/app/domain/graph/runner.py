"""Graph-invocation helpers shared between the sync and live-progress endpoints.

|| Helpers de invocación del grafo compartidos entre el endpoint sincrónico y
el de progreso en vivo.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import get_settings
from app.dependencies import get_activity_log, get_embedder, get_reranker
from app.domain.graph.activity import describe_node
from app.domain.profiles import synthesizer_runtime
from app.domain.schemas import AnswerAgentState
from app.foundation.persistence.database import get_async_session_factory
from app.generation.rag.retrieval.hybrid import HybridRetriever
from app.generation.rag.schemas import AnswerRequest
from app.generation.rag.store.repository import ChunkRepository

log = structlog.get_logger()

THREAD_PREFIX = "answer-agent"


def thread_config(
    thread_id: str,
    *,
    retriever: Any,
    llm: Any,
    reranker: Any,
    persona: str | None = None,
) -> dict:
    """Runnable config for one graph thread. || Config del runnable para un hilo del grafo."""
    return {
        "configurable": {
            "thread_id": f"{THREAD_PREFIX}:{thread_id}",
            "retriever": retriever,
            "llm": llm,
            "reranker": reranker,
            "persona": persona,
        }
    }




def initial_state(body: AnswerRequest) -> AnswerAgentState:
    """Seed state for a fresh run. || Estado semilla para una corrida nueva."""
    return {
        "query": body.question,
        "retrieval_options": {
            "limit": body.limit,
            "max_per_document": body.max_per_document,
            "lexical": body.lexical,
            "split": body.split,
            "rerank": body.rerank,
        },
        "supervisor_steps": 0,
        "retrieval_attempts": 0,
        "routing_history": [],
        "agent_contributions": [],
        "review_reasons": [],
    }


def completed_result(values: dict, fallback_question: str) -> dict:
    """Shape a completed run's values into the progress/response payload.

    || Da forma a los values de una corrida completa para el payload de progreso/respuesta.
    """
    return {
        "question": values.get("query") or fallback_question,
        "answer": values.get("answer") or "",
        "citations": list(values.get("citations") or []),
        "grounded": bool(values.get("citations_valid", True)),
        "confidence": values.get("confidence"),
        "needs_human_review": bool(values.get("needs_human_review")),
        "review_reasons": list(values.get("review_reasons") or []),
        "routing_history": list(values.get("routing_history") or []),
    }


def paused_result(values: dict, fallback_question: str, reasons: list[str]) -> dict:
    """Shape a paused run's values into the progress/response payload.

    || Da forma a los values de una corrida pausada para el payload de progreso/respuesta.
    """
    return {
        "question": values.get("query") or fallback_question,
        "answer": values.get("answer"),
        "citations": list(values.get("citations") or []),
        "review_reasons": reasons,
        "confidence": values.get("confidence"),
    }


async def _stream_and_log(
    thread_id: str,
    body: AnswerRequest,
    graph: Any,
    *,
    retriever: Any,
    llm: Any,
    reranker: Any,
    persona: str | None = None,
):
    """Run the graph via ``astream``, narrating each node into the activity log.

    || Corre el grafo vía ``astream``, narrando cada nodo en el log de actividad.
    """
    activity_log = get_activity_log()
    config = thread_config(
        thread_id, retriever=retriever, llm=llm, reranker=reranker, persona=persona
    )

    async for update in graph.astream(initial_state(body), config, stream_mode="updates"):
        for node_name, node_update in update.items():
            for entry in describe_node(node_name, node_update):
                activity_log.append(thread_id, entry["node"], entry["label"], entry["message"])

    return await graph.aget_state(config)


async def run_agentic_background(thread_id: str, body: AnswerRequest, graph: Any) -> None:
    """Run the graph end-to-end (or to its first pause) with live activity.

    Opens its OWN database session: the request that scheduled this as a
    background task returns before FastAPI would close the session it
    injected there, so this cannot reuse it.

    || Corre el grafo de punta a punta (o hasta su primera pausa) con
    actividad en vivo. Abre su PROPIA sesión de base: el request que agendó
    esta tarea en background vuelve antes de que FastAPI cierre la sesión que
    le inyectó ahí, así que esto no puede reusarla.
    """
    activity_log = get_activity_log()
    activity_log.start(thread_id)
    session_factory = get_async_session_factory()

    try:
        async with session_factory() as session:
            retriever = HybridRetriever(ChunkRepository(session), get_embedder())
            reranker = get_reranker() if body.rerank else None
            llm, persona = await synthesizer_runtime(
                session, get_settings(), profile_id=body.profile_id
            )
            snapshot = await _stream_and_log(
                thread_id,
                body,
                graph,
                retriever=retriever,
                llm=llm,
                reranker=reranker,
                persona=persona,
            )
    except Exception as exc:  # noqa: BLE001 — a background failure must not vanish silently.
        log.error("answer_agentic_background_failed", thread_id=thread_id, error=str(exc)[:300])
        activity_log.finish(thread_id, "failed", error=str(exc)[:300])
        return

    values = snapshot.values or {}
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if snapshot.next and interrupts:
        payload = interrupts[0].value or {}
        reasons = list(payload.get("reasons") or values.get("review_reasons") or [])
        activity_log.finish(
            thread_id, "awaiting_human_review", result=paused_result(values, body.question, reasons)
        )
        return

    activity_log.finish(thread_id, "completed", result=completed_result(values, body.question))
