"""POST /answer/agentic — LangGraph orchestration over RAG.

Thin transport: builds initial state, invokes ``app.state.answer_graph``, maps
human-review pauses to HTTP 202. Reuses the same retrieval and generation pieces
as ``POST /answer`` — does not reimplement them.

Also exposes a live-progress variant (``/start`` + ``/{thread_id}/progress``)
for a frontend that wants to show the four agents working as they go, instead
of a blank screen until the single blocking call returns. Both variants share
the same graph, the same agents, and the same checkpointer thread — ``/start``
just runs it via ``astream`` in a background task and narrates each node into
``GraphActivityLog`` instead of awaiting the whole thing inline.

|| POST /answer/agentic — orquestación LangGraph sobre RAG. Transporte delgado:
arma el estado inicial, invoca ``app.state.answer_graph``, mapea pausas de
revisión humana a HTTP 202.

También expone una variante de progreso en vivo (``/start`` +
``/{thread_id}/progress``) para un frontend que quiera mostrar a los cuatro
agentes trabajando a medida que avanzan, en vez de una pantalla en blanco
hasta que vuelve la llamada bloqueante única.
"""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_activity_log, get_embedder, get_reranker
from app.domain.graph.runner import (
    THREAD_PREFIX as _THREAD_PREFIX,
)
from app.domain.graph.runner import (
    completed_result,
    initial_state,
    run_agentic_background,
    thread_config,
)
from app.domain.profiles import (
    ProfileResolutionError,
    load_synthesizer_profile,
    synthesizer_runtime,
)
from app.foundation.persistence.database import get_async_session
from app.generation.rag.retrieval.hybrid import HybridRetriever
from app.generation.rag.schemas import AnswerRequest, SearchHit
from app.generation.rag.store.repository import ChunkRepository

router = APIRouter(prefix="/answer/agentic", tags=["answer-agentic"])
log = structlog.get_logger()

# Strong references to in-flight background runs. asyncio does not keep a
# task alive on its own once nothing holds it — a fire-and-forget task with
# no reference can be garbage-collected mid-run, silently.
# || Referencias fuertes a corridas en background en curso. asyncio no
# mantiene viva una tarea sola una vez que nada la referencia — una tarea
# fire-and-forget sin referencia puede ser recolectada a mitad de camino, en
# silencio.
_BACKGROUND_RUNS: set[asyncio.Task] = set()


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


class GraphActivityEntry(BaseModel):
    """One narrated line of live agent activity. || Una línea narrada de actividad en vivo."""

    node: str
    label: str
    message: str
    at: float


class AnswerAgenticStartResponse(BaseModel):
    """Ack for a run just scheduled in the background. || Ack de una corrida agendada en background."""

    status: Literal["running"] = "running"
    thread_id: str = Field(description="Poll ``/{thread_id}/progress`` with this. || Consultar con esto.")


class AnswerAgenticProgress(BaseModel):
    """Live status of a background agentic run. || Estado en vivo de una corrida agentica en background."""

    status: Literal["running", "completed", "awaiting_human_review", "failed"]
    thread_id: str
    activity: list[GraphActivityEntry] = Field(default_factory=list)
    question: str | None = None
    answer: str | None = None
    citations: list[SearchHit] = Field(default_factory=list)
    grounded: bool | None = None
    confidence: float | None = None
    needs_human_review: bool | None = None
    review_reasons: list[str] = Field(default_factory=list)
    routing_history: list[dict] = Field(default_factory=list)
    error: str | None = Field(
        default=None, description="Set only when status='failed'. || Solo cuando status='failed'."
    )


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
    try:
        llm, persona, guardrails = await synthesizer_runtime(
            session, get_settings(), profile_id=body.profile_id
        )
    except ProfileResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail
        ) from exc
    config = thread_config(
        thread_id,
        retriever=retriever,
        llm=llm,
        reranker=reranker,
        persona=persona,
        guardrails=guardrails,
    )

    try:
        await graph.ainvoke(initial_state(body), config)
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
    llm, persona, guardrails = await synthesizer_runtime(session, get_settings())
    config = thread_config(
        bare_thread,
        retriever=retriever,
        llm=llm,
        reranker=get_reranker(),
        persona=persona,
        guardrails=guardrails,
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

    values = snapshot.values or {}
    # Best-effort: a thread resumed straight from `POST /answer/agentic`
    # (the synchronous path) never had an activity buffer, so there is
    # nothing to append to — `get_activity_log().read()` would be `None` and
    # `.finish()` would create an orphaned entry nobody polls. Only threads
    # started via `/start` benefit from this, and only if their buffer is
    # still there.
    # || A lo sumo: un hilo resumido directo desde `POST /answer/agentic` (el
    # camino sincrónico) nunca tuvo buffer de actividad — no hay nada a lo
    # que agregarle. Solo los hilos arrancados vía `/start` se benefician de
    # esto, y solo si su buffer sigue ahí.
    activity_log = get_activity_log()
    if activity_log.read(bare_thread) is not None:
        action = body.decision
        message = f"decisión humana: {action}" + (f" — {body.note}" if body.note else "")
        activity_log.append(bare_thread, "answer_review_gate", "Gate de revisión", message)
        activity_log.finish(bare_thread, "completed", result=completed_result(values, ""))

    return _completed_response(bare_thread, values)


@router.post(
    "/start",
    response_model=AnswerAgenticStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def answer_agentic_start(
    body: AnswerRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
):
    """Schedule the agentic answer graph in the background and return at once.

    Poll ``GET /{thread_id}/progress`` to watch the four agents work and to
    read the final answer (or the human-review pause) once it lands.

    A bad ``profile_id`` is rejected here, before the graph is scheduled,
    so the client gets 422 instead of a run that fails on first poll.

    || Agenda el grafo agentico en background y vuelve al instante. Un
    ``profile_id`` inválido se rechaza acá, antes de agendar el grafo.
    """
    graph = _require_graph(request)
    if body.profile_id:
        try:
            await load_synthesizer_profile(session, profile_id=body.profile_id)
        except ProfileResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail
            ) from exc
    thread_id = str(uuid4())

    task = asyncio.create_task(run_agentic_background(thread_id, body, graph))
    _BACKGROUND_RUNS.add(task)
    task.add_done_callback(_BACKGROUND_RUNS.discard)

    return AnswerAgenticStartResponse(thread_id=thread_id)


@router.get("/{thread_id}/progress", response_model=AnswerAgenticProgress)
async def answer_agentic_progress(thread_id: str):
    """Current activity and, once available, the result for ``thread_id``.

    || Actividad actual y, cuando está disponible, el resultado de ``thread_id``.
    """
    run = get_activity_log().read(thread_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired thread_id. Did you call POST /start first? "
            "|| thread_id desconocido o expirado. ¿Llamaste antes a POST /start?",
        )

    activity = [
        GraphActivityEntry(node=entry.node, label=entry.label, message=entry.message, at=entry.at)
        for entry in run.entries
    ]

    if run.status in ("running", "failed"):
        return AnswerAgenticProgress(
            status=run.status,
            thread_id=thread_id,
            activity=activity,
            error=run.error,
        )

    result = run.result or {}
    return AnswerAgenticProgress(
        status=run.status,
        thread_id=thread_id,
        activity=activity,
        question=result.get("question"),
        answer=result.get("answer"),
        citations=[SearchHit.model_validate(hit) for hit in result.get("citations") or []],
        grounded=result.get("grounded"),
        confidence=result.get("confidence"),
        needs_human_review=result.get("needs_human_review"),
        review_reasons=result.get("review_reasons") or [],
        routing_history=result.get("routing_history") or [],
    )
