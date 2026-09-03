"""POST /answer/agentic — LangGraph orchestration over RAG.

Thin transport: builds initial state, invokes ``app.state.answer_graph``, maps
human-review pauses to HTTP 202. Reuses the same retrieval and generation pieces
as ``POST /answer`` — does not reimplement them.

|| POST /answer/agentic — orquestación LangGraph sobre RAG. Transporte delgado:
arma el estado inicial, invoca ``app.state.answer_graph``, mapea pausas de
revisión humana a HTTP 202.
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_answer_llm, get_embedder, get_reranker
from app.domain.schemas import AnswerAgentState, RetrievalOptions
from app.foundation.persistence.database import get_async_session
from app.generation.rag.retrieval.hybrid import HybridRetriever
from app.generation.rag.schemas import AnswerRequest, SearchHit
from app.generation.rag.store.repository import ChunkRepository

router = APIRouter(prefix="/answer/agentic", tags=["answer-agentic"])
log = structlog.get_logger()

_THREAD_PREFIX = "answer-agent"


class AnswerAgenticResponse(BaseModel):
    """Completed agentic answer. || Respuesta agentica completada."""

    status: Literal["completed"] = "completed"
    thread_id: str = Field(description="Graph thread id for audit. || Id de hilo del grafo.")
    question: str
    answer: str
    citations: list[SearchHit]
    grounded: bool = Field(
        description="True when inline citations match retrieved hits. "
        "|| True cuando las citas inline coinciden con los hits recuperados."
    )
    confidence: float | None = None
    needs_human_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    routing_history: list[dict] = Field(default_factory=list)


class AnswerAgenticPausedResponse(BaseModel):
    """Graph paused for human review. || Grafo pausado para revisión humana."""

    status: Literal["awaiting_human_review"] = "awaiting_human_review"
    thread_id: str
    question: str
    answer: str | None = None
    citations: list[SearchHit] = Field(default_factory=list)
    review_reasons: list[str]
    confidence: float | None = None


class AnswerAgenticResumeRequest(BaseModel):
    """Payload to resume a paused graph. || Payload para resumir un grafo pausado."""

    thread_id: str = Field(min_length=1)
    decision: Literal["approve", "reject", "adjust"] = "approve"
    note: str | None = None


def _thread_config(thread_id: str, *, retriever, llm, reranker) -> dict:
    return {
        "configurable": {
            "thread_id": f"{_THREAD_PREFIX}:{thread_id}",
            "retriever": retriever,
            "llm": llm,
            "reranker": reranker,
        }
    }


def _initial_state(body: AnswerRequest) -> AnswerAgentState:
    return {
        "query": body.question,
        "retrieval_options": RetrievalOptions(
            limit=body.limit,
            max_per_document=body.max_per_document,
            lexical=body.lexical,
            split=body.split,
            rerank=body.rerank,
        ),
        "supervisor_steps": 0,
        "retrieval_attempts": 0,
        "routing_history": [],
        "agent_contributions": [],
        "review_reasons": [],
    }


def _hits_from_state(values: dict) -> list[SearchHit]:
    return [SearchHit.model_validate(hit) for hit in (values.get("citations") or [])]


def _completed_response(thread_id: str, values: dict) -> AnswerAgenticResponse:
    return AnswerAgenticResponse(
        thread_id=thread_id,
        question=values.get("query") or "",
        answer=values.get("answer") or "",
        citations=_hits_from_state(values),
        grounded=bool(values.get("citations_valid", True)),
        confidence=values.get("confidence"),
        needs_human_review=bool(values.get("needs_human_review")),
        review_reasons=list(values.get("review_reasons") or []),
        routing_history=list(values.get("routing_history") or []),
    )


def _paused_response(thread_id: str, question: str, values: dict, reasons: list[str]):
    return AnswerAgenticPausedResponse(
        thread_id=thread_id,
        question=question,
        answer=values.get("answer"),
        citations=_hits_from_state(values),
        review_reasons=reasons,
        confidence=values.get("confidence"),
    )


def _require_graph(request: Request):
    graph = getattr(request.app.state, "answer_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer graph is not available (checkpointer or compile failed). "
            "|| El grafo de respuestas no está disponible.",
        )
    return graph


def _strip_prefix(thread_id: str) -> str:
    prefix = f"{_THREAD_PREFIX}:"
    return thread_id.removeprefix(prefix) if thread_id.startswith(prefix) else thread_id


@router.post(
    "",
    response_model=AnswerAgenticResponse,
    responses={status.HTTP_202_ACCEPTED: {"model": AnswerAgenticPausedResponse}},
)
async def answer_agentic(
    body: AnswerRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
):
    """Run the agentic answer graph for ``body.question``.

    Returns 202 when the human-review gate pauses the flow.

    || Corre el grafo agentico de respuesta para ``body.question``. Devuelve 202
    cuando el gate de revisión humana pausa el flujo.
    """
    graph = _require_graph(request)
    thread_id = str(uuid4())
    retriever = HybridRetriever(ChunkRepository(session), get_embedder())
    reranker = get_reranker() if body.rerank else None
    config = _thread_config(
        thread_id,
        retriever=retriever,
        llm=get_answer_llm(),
        reranker=reranker,
    )

    try:
        await graph.ainvoke(_initial_state(body), config)
        snapshot = await graph.aget_state(config)
    except Exception as exc:
        log.error("answer_agentic_failed", error_type=type(exc).__name__, error=str(exc)[:300])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to produce an agentic answer. "
            "|| Falló la producción de una respuesta agentica.",
        ) from exc

    values = snapshot.values or {}
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if snapshot.next and interrupts:
        payload = interrupts[0].value or {}
        reasons = list(payload.get("reasons") or values.get("review_reasons") or [])
        paused = _paused_response(thread_id, body.question, values, reasons)
        return Response(
            content=paused.model_dump_json(),
            status_code=status.HTTP_202_ACCEPTED,
            media_type="application/json",
        )

    return _completed_response(thread_id, values)


@router.post("/resume", response_model=AnswerAgenticResponse)
async def answer_agentic_resume(
    body: AnswerAgenticResumeRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
):
    """Resume a paused graph with a human decision.

    || Resume un grafo pausado con una decisión humana.
    """
    graph = _require_graph(request)
    bare_thread = _strip_prefix(body.thread_id)
    retriever = HybridRetriever(ChunkRepository(session), get_embedder())
    config = _thread_config(
        bare_thread,
        retriever=retriever,
        llm=get_answer_llm(),
        reranker=get_reranker(),
    )

    snapshot = await graph.aget_state(config)
    if not snapshot.next:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No pending human review for this thread_id. "
            "|| No hay revisión humana pendiente para este thread_id.",
        )

    try:
        await graph.ainvoke(
            Command(resume={"decision": body.decision, "note": body.note}),
            config,
        )
        snapshot = await graph.aget_state(config)
    except Exception as exc:
        log.error(
            "answer_agentic_resume_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to resume the agentic answer. "
            "|| Falló la reanudación de la respuesta agentica.",
        ) from exc

    return _completed_response(bare_thread, snapshot.values or {})
