"""Live activity log for the answer-orchestration graph.

A graph that runs end-to-end inside one blocking call gives the frontend
nothing to show while it works — no polling target exists until the run is
already over. This module bridges that gap the same way the course's
``agents_event`` branch does: consume ``graph.astream(..., stream_mode=
"updates")`` node by node, translate each raw update into a human-readable
line with ``describe_node``, and buffer those lines per ``thread_id`` so a
``GET .../progress`` endpoint has something to return while the run is still
going.

No Redis: a single in-process dict is enough for this project's traffic —
the course's Redis-backed variant exists for multi-worker deployments, which
this service does not have (one instance, one event loop, one dict). The day
a second worker process shows up, THAT is the signal to swap this for a
shared backend, not before.

|| Log de actividad en vivo del grafo de orquestación de respuestas. Un grafo
que corre de punta a punta dentro de una sola llamada bloqueante no le da al
frontend nada que mostrar mientras trabaja. Este módulo tapa ese hueco igual
que la rama ``agents_event`` del curso: consume ``graph.astream(...,
stream_mode="updates")`` nodo por nodo, traduce cada update crudo a una línea
legible con ``describe_node``, y bufferea esas líneas por ``thread_id``.

Sin Redis: un dict de un solo proceso alcanza para el tráfico de este
proyecto — la variante con Redis del curso existe para despliegues
multi-worker, que este servicio no tiene. El día que aparezca un segundo
worker, ESA es la señal para cambiarlo, no antes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE

log = structlog.get_logger()

RunStatus = Literal["running", "completed", "awaiting_human_review", "failed"]

_LABELS: dict[str, str] = {
    "orchestrator": "Orquestador",
    "query_planner": "Planificador de consulta",
    "evidence_retriever": "Recuperación de evidencia",
    "answer_synthesizer": "Síntesis de respuesta",
    "citation_validator": "Validación de citas",
    "answer_review_gate": "Gate de revisión",
}


@dataclass
class ActivityEntry:
    """One narrated line of graph activity. || Una línea narrada de actividad del grafo."""

    node: str
    label: str
    message: str
    at: float = field(default_factory=time.time)


@dataclass
class _Run:
    status: RunStatus = "running"
    entries: list[ActivityEntry] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None


class GraphActivityLog:
    """Per-``thread_id`` activity buffer for live progress polling.

    || Buffer de actividad por ``thread_id`` para el polling de progreso en vivo.
    """

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}

    def start(self, thread_id: str) -> None:
        """Reset (or open) the buffer for a fresh run. || Reinicia (o abre) el buffer."""
        self._runs[thread_id] = _Run()

    def append(self, thread_id: str, node: str, label: str, message: str) -> None:
        """Append one narrated line. || Agrega una línea narrada."""
        run = self._runs.setdefault(thread_id, _Run())
        run.entries.append(ActivityEntry(node=node, label=label, message=message))

    def finish(
        self,
        thread_id: str,
        status: RunStatus,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Record the terminal status and payload. || Registra el estado final y su payload."""
        run = self._runs.setdefault(thread_id, _Run())
        run.status = status
        run.result = result
        run.error = error

    def read(self, thread_id: str) -> _Run | None:
        """Current buffer for ``thread_id``, or ``None`` if unknown. || Buffer actual, o ``None``."""
        return self._runs.get(thread_id)


def describe_node(node_name: str, update: Any) -> list[dict[str, str]]:
    """Translate one node's raw update into human-readable activity lines.

    Pure and exception-free: this runs inside a live streaming loop, where a
    formatting bug must never take down the run it only narrates — an
    unrecognized shape degrades to a generic line instead of raising.

    || Traduce el update crudo de un nodo a líneas de actividad legibles.
    Pura y sin excepciones: esto corre dentro de un loop de streaming en
    vivo, donde un bug de formato nunca debe tirar abajo la corrida que solo
    está narrando — una forma no reconocida degrada a una línea genérica en
    vez de lanzar.
    """
    try:
        return _describe(node_name, update)
    except Exception:  # noqa: BLE001 — narration must never break the run.
        label = _LABELS.get(node_name, node_name)
        return [{"node": node_name, "label": label, "message": "…"}]


def _describe(node_name: str, update: Any) -> list[dict[str, str]]:
    if node_name == "__interrupt__":
        return _describe_interrupt(update)

    update = update or {}
    label = _LABELS.get(node_name, node_name)

    if node_name == "orchestrator":
        target = update.get("next_agent") or "?"
        history = update.get("routing_history") or []
        source = history[-1].get("source") if history else None
        message = f"→ {target}" + (f" ({source})" if source else "")
        return [{"node": node_name, "label": label, "message": message}]

    if node_name == "query_planner":
        sub_queries = update.get("sub_queries") or []
        filters = update.get("filters") or {}
        message = f"{len(sub_queries)} subconsulta(s)"
        if filters:
            message += f" · filtros sugeridos: {filters}"
        return [{"node": node_name, "label": label, "message": message}]

    if node_name == "evidence_retriever":
        hits = update.get("hits") or []
        message = f"{len(hits)} chunk(s) recuperados del corpus"
        return [{"node": node_name, "label": label, "message": message}]

    if node_name == "answer_synthesizer":
        answer = update.get("answer") or ""
        citations = update.get("citations") or []
        if answer == INSUFFICIENT_CONTEXT_MESSAGE:
            message = "sin evidencia suficiente para responder"
        else:
            message = f"respuesta generada ({len(answer)} caracteres) sobre {len(citations)} chunk(s)"
        return [{"node": node_name, "label": label, "message": message}]

    if node_name == "citation_validator":
        grounded = update.get("citations_valid")
        confidence = update.get("confidence")
        if update.get("requery_requested"):
            message = "cita sin respaldo → pidiendo nueva evidencia"
        elif update.get("needs_human_review"):
            message = "sin respaldo suficiente → revisión humana"
        elif grounded:
            message = "citas respaldadas"
            if confidence is not None:
                message += f" · confianza {confidence:.0%}"
        else:
            message = "validación completada"
        return [{"node": node_name, "label": label, "message": message}]

    if node_name == "answer_review_gate":
        decision = update.get("human_decision")
        if decision is not None:
            action = (decision or {}).get("decision") or (decision or {}).get("action") or "approve"
            message = f"decisión humana: {action}"
        elif update.get("needs_human_review"):
            message = "esperando revisión humana"
        else:
            message = "sin disparadores → respuesta lista"
        return [{"node": node_name, "label": label, "message": message}]

    return [{"node": node_name, "label": label, "message": "actualizó el estado"}]


def _describe_interrupt(update: Any) -> list[dict[str, str]]:
    reasons: list[str] = []
    try:
        for item in update or ():
            value = getattr(item, "value", None) or {}
            reasons.extend(value.get("reasons") or [])
    except TypeError:
        pass
    message = "esperando revisión humana"
    if reasons:
        message += ": " + "; ".join(reasons)
    return [
        {
            "node": "answer_review_gate",
            "label": _LABELS["answer_review_gate"],
            "message": f"⏸ {message}",
        }
    ]
