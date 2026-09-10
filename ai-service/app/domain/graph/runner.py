"""Graph-invocation helpers shared between the sync and live-progress endpoints.

|| Helpers de invocación del grafo compartidos entre el endpoint sincrónico y
el de progreso en vivo.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import get_settings
from app.dependencies import get_activity_log, get_embedder, get_reranker
from app.domain.business_db_store import ActiveRun, resolve_active_run
from app.domain.graph.activity import describe_node
from app.domain.profiles import synthesizer_runtime
from app.domain.schemas import AnswerAgentState, QueryFilters
from app.foundation.llm.wrapper import usage_payload
from app.foundation.persistence.database import get_async_session_factory
from app.foundation.persistence.usage import PURPOSE_SYNTHESIZER, llm_with_accounting
from app.generation.conversation.anchors import detect_anchors
from app.generation.conversation.facts import facts_from_turn
from app.generation.conversation.models import (
    DEFAULT_TITLE_MAX_CHARS,
    CitationSnapshot,
    ConversationSession,
    HistoryTurn,
    Turn,
)
from app.generation.conversation.store import SessionStore
from app.generation.rag.retrieval.hybrid import HybridRetriever
from app.generation.rag.schemas import AnswerRequest
from app.generation.rag.store.repository import ChunkRepository

log = structlog.get_logger()

THREAD_PREFIX = "answer-agent"

# How much of an answer the session keeps. The window is there so the model
# knows what was already said, not so it can re-read itself: storing the prose
# verbatim would spend on repetition the budget that belongs to evidence.
# || Cuánto de una respuesta guarda la sesión. La ventana existe para que el
# modelo sepa qué se dijo, no para que se relea: guardar la prosa entera
# gastaría en repetición el presupuesto que le corresponde a la evidencia.
TURN_ANSWER_MAX_CHARS = 600


def thread_config(
    thread_id: str,
    *,
    retriever: Any,
    llm: Any,
    reranker: Any,
    persona: str | None = None,
    guardrails: str | None = None,
) -> dict:
    """Runnable config for one graph thread. || Config del runnable para un hilo del grafo."""
    return {
        "configurable": {
            "thread_id": f"{THREAD_PREFIX}:{thread_id}",
            "retriever": retriever,
            "llm": llm,
            "reranker": reranker,
            "persona": persona,
            "guardrails": guardrails,
        }
    }


def initial_state(
    body: AnswerRequest,
    conversation: ConversationSession | None = None,
    active_run: ActiveRun | None = None,
) -> AnswerAgentState:
    """Seed state for a fresh run. || Estado semilla para una corrida nueva.

    Without a ``conversation`` the memory fields stay absent and every node
    behaves exactly as it did before sessions existed — which is what makes
    ``session_id`` safe to leave optional on the request.

    || Sin ``conversation`` los campos de memoria quedan ausentes y cada nodo
    se comporta igual que antes de que existieran las sesiones, que es lo que
    hace seguro dejar ``session_id`` opcional en el request.
    """
    # The filters the client asked for. Seeded here and resolved by the
    # planner, which is the one node that sees all three sources; the retriever
    # reads only the resolved `filters` and knows nothing about the policy.
    # A field the client did not send is NOT seeded: absent means "no narrowing
    # asked for", which is not the same as an empty list.
    # || Los filtros que pidió el cliente. Se siembran acá y los resuelve el
    # planner, que es el único nodo que ve las tres fuentes; el retriever lee
    # solo los `filters` resueltos y no conoce la política. Un campo que el
    # cliente no mandó NO se siembra: ausente significa «no pidió recorte», que
    # no es lo mismo que una lista vacía.
    request_filters: QueryFilters = {}
    if body.module_code:
        request_filters["module_code"] = list(body.module_code)
    if body.window_type_name:
        request_filters["window_type_name"] = list(body.window_type_name)

    state: AnswerAgentState = {
        "query": body.question,
        "resolved_question": body.question,
        "resolved_referents": [],
        "request_filters": request_filters,
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
    # Resolved by the caller, which is the one that has a database session, and
    # frozen into the state here. Absent means "no active run", and then the
    # evidence block falls back to the stamped column -- see
    # `context_budget.resolve_window_status`.
    # || La resuelve quien llama, que es el que tiene sesión de base, y se
    # congela acá. Ausente significa «no hay corrida activa», y entonces el
    # bloque de evidencia cae a la columna estampada.
    if active_run is not None:
        state["active_run_id"] = active_run.run_id
        state["active_run_env"] = active_run.env
    if conversation is not None:
        state["session_id"] = conversation.session_id
        state["conversation_facts"] = conversation.facts.model_dump(mode="json")
        state["conversation_anchors"] = [
            anchor.model_dump(mode="json") for anchor in conversation.anchors
        ]
        state["conversation_turns"] = [
            turn.model_dump(mode="json") for turn in conversation.turns
        ]
    return state


async def open_turn(
    store: SessionStore, body: AnswerRequest
) -> ConversationSession | None:
    """Load the session this request names and pin whatever it declares.

    ``None`` covers three cases the caller does not need to tell apart: no
    ``session_id`` was sent, the session does not exist, or it is past its
    TTL. All three answer the turn without memory, which is the behavior that
    existed before sessions did.

    Pinning happens on the way IN, not on the way out: a question that says
    "de acá en adelante, solo módulo CA" has to constrain the retrieval of
    that very turn. Pinning it after the answer would make the first turn the
    one exception to the rule the user just set.

    || Carga la sesión que nombra este request y fija lo que declare. ``None``
    cubre tres casos que quien llama no distingue: sin ``session_id``, sesión
    inexistente, o vencida — los tres responden sin memoria. El fijado ocurre
    a la ENTRADA y no a la salida: una pregunta que dice «de acá en adelante,
    solo módulo CA» tiene que acotar la recuperación de ese mismo turno.
    Fijarla después de responder haría del primer turno la única excepción a
    la regla que el usuario acaba de poner.
    """
    session_id = getattr(body, "session_id", None)
    if not session_id:
        return None

    conversation = await store.get(session_id)
    if conversation is None:
        log.info("conversation_session_unavailable", session_id=session_id)
        return None

    pinned = conversation.pin(detect_anchors(body.question))
    if pinned:
        await store.save(conversation)
    return conversation


async def close_turn(
    store: SessionStore,
    conversation: ConversationSession | None,
    values: dict,
    *,
    written_question: str,
    max_turns: int,
    answer_preview_chars: int = TURN_ANSWER_MAX_CHARS,
    title_max_chars: int = DEFAULT_TITLE_MAX_CHARS,
) -> None:
    """Record one finished exchange on the session, exactly once.

    Called where a run REACHES ITS END — not where the graph pauses. A run
    stopped at the human-review gate has not produced an answer the user
    accepted, and writing it would leave the session remembering a turn that
    may still be rejected.

    The memory window stores a trimmed answer so the model knows what was
    already said without spending the evidence budget on prose. The
    transcript stores the full answer and a citation snapshot so a reload
    does not drop provenance.

    || Registra un intercambio terminado en la sesión, exactamente una vez.
    Se llama donde una corrida TERMINA, no donde el grafo pausa. La ventana
    guarda la respuesta recortada; el transcript, la prosa entera y un
    snapshot de citas para que un reload no pierda procedencia.
    """
    if conversation is None:
        return

    answer = values.get("answer") or ""
    raw_citations = [hit for hit in (values.get("citations") or []) if isinstance(hit, dict)]
    cited = [str(hit["document_id"]) for hit in raw_citations if hit.get("document_id")]
    snapshots = [
        snapshot
        for snapshot in (CitationSnapshot.from_hit(hit) for hit in raw_citations)
        if snapshot is not None
    ]
    written = values.get("query") or written_question
    resolved = values.get("resolved_question") or written
    conversation.facts = conversation.facts.merge_with(
        facts_from_turn(
            question=written,
            filters=dict(values.get("filters") or {}),
            cited_document_ids=list(dict.fromkeys(cited)),
        )
    )
    conversation.append_turn(
        Turn(question=written, resolved_question=resolved, answer=answer[:answer_preview_chars]),
        max_turns=max_turns,
    )
    conversation.append_history(
        HistoryTurn(
            question=written,
            resolved_question=resolved,
            answer=answer,
            citations=snapshots,
            grounded=bool(values.get("citations_valid", True)),
        ),
        title_max_chars=title_max_chars,
    )
    await store.save(conversation)
    log.info(
        "conversation_turn_closed",
        session_id=conversation.session_id,
        turns=len(conversation.turns),
        history=len(conversation.history),
        anchors=len(conversation.anchors),
        cited=len(cited),
    )


_FILTER_FIELDS = ("module_code", "window_type_name", "transaction_prefix")


def effective_filters(values: dict) -> list[dict]:
    """The resolved retrieval filters with the source of each one.

    One implementation for both the synchronous responses and the background
    payloads: two would drift, and this is the field whose whole point is
    saying WHY the search was narrowed.

    || Los filtros de recuperación resueltos con la fuente de cada uno. Una
    sola implementación para las respuestas sincrónicas y para los payloads de
    background: dos se desincronizarían, y justamente este campo existe para
    decir POR QUÉ se recortó la búsqueda.
    """
    resolved = values.get("filters") or {}
    sources = values.get("filter_sources") or {}
    return [
        {"field": field, "values": list(resolved[field]), "source": sources.get(field, "question")}
        for field in _FILTER_FIELDS
        if resolved.get(field)
    ]


def completed_result(values: dict, fallback_question: str) -> dict:
    """Shape a completed run's values into the progress/response payload.

    || Da forma a los values de una corrida completa para el payload de progreso/respuesta.
    """
    return {
        "question": values.get("query") or fallback_question,
        "resolved_question": values.get("resolved_question")
        or values.get("query")
        or fallback_question,
        "resolved_referents": list(values.get("resolved_referents") or []),
        "session_memory_used": bool(values.get("session_id")),
        "anchors_applied": list(values.get("conversation_anchors") or []),
        "effective_filters": effective_filters(values),
        "answer": values.get("answer") or "",
        "citations": list(values.get("citations") or []),
        "grounded": bool(values.get("citations_valid", True)),
        "confidence": values.get("confidence"),
        "needs_human_review": bool(values.get("needs_human_review")),
        "review_reasons": list(values.get("review_reasons") or []),
        "routing_history": list(values.get("routing_history") or []),
        "context_truncated": bool(values.get("context_truncated")),
        "dropped_hits": int(values.get("dropped_hits") or 0),
        "answer_truncated": bool(values.get("answer_truncated")),
        "usage": values.get("usage") or usage_payload(),
    }


def paused_result(values: dict, fallback_question: str, reasons: list[str]) -> dict:
    """Shape a paused run's values into the progress/response payload.

    || Da forma a los values de una corrida pausada para el payload de progreso/respuesta.
    """
    return {
        "question": values.get("query") or fallback_question,
        "resolved_question": values.get("resolved_question")
        or values.get("query")
        or fallback_question,
        "resolved_referents": list(values.get("resolved_referents") or []),
        "session_memory_used": bool(values.get("session_id")),
        "anchors_applied": list(values.get("conversation_anchors") or []),
        "effective_filters": effective_filters(values),
        "answer": values.get("answer"),
        "citations": list(values.get("citations") or []),
        "review_reasons": reasons,
        "confidence": values.get("confidence"),
        "context_truncated": bool(values.get("context_truncated")),
        "dropped_hits": int(values.get("dropped_hits") or 0),
        "answer_truncated": bool(values.get("answer_truncated")),
        "usage": values.get("usage") or usage_payload(),
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
    guardrails: str | None = None,
    conversation=None,
    active_run: ActiveRun | None = None,
):
    """Run the graph via ``astream``, narrating each node into the activity log.

    || Corre el grafo vía ``astream``, narrando cada nodo en el log de actividad.
    """
    activity_log = get_activity_log()
    config = thread_config(
        thread_id,
        retriever=retriever,
        llm=llm,
        reranker=reranker,
        persona=persona,
        guardrails=guardrails,
    )

    seed = initial_state(body, conversation, active_run)
    async for update in graph.astream(seed, config, stream_mode="updates"):
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

    settings = get_settings()
    try:
        async with session_factory() as session:
            retriever = HybridRetriever(ChunkRepository(session), get_embedder())
            reranker = get_reranker() if body.rerank else None
            runtime = await synthesizer_runtime(
                session, settings, profile_id=body.profile_id
            )
            store = SessionStore(session, ttl_days=settings.CONVERSATION_SESSION_TTL_DAYS)
            conversation = await open_turn(store, body)
            llm = llm_with_accounting(
                runtime.llm,
                purpose=PURPOSE_SYNTHESIZER,
                provider_id=runtime.provider_id,
                tenant_id=settings.TENANT_ID,
                session_id=conversation.session_id if conversation else None,
                thread_id=thread_id,
            )
            snapshot = await _stream_and_log(
                thread_id,
                body,
                graph,
                retriever=retriever,
                llm=llm,
                reranker=reranker,
                persona=runtime.persona,
                guardrails=runtime.guardrails,
                conversation=conversation,
                active_run=await resolve_active_run(session, settings),
            )
            values = snapshot.values or {}
            interrupts = getattr(snapshot, "interrupts", None) or ()
            if not (snapshot.next and interrupts):
                await close_turn(
                    store,
                    conversation,
                    values,
                    written_question=body.question,
                    max_turns=settings.CONVERSATION_MAX_TURNS,
                    title_max_chars=settings.CONVERSATION_TITLE_MAX_CHARS,
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
