"""Conversation sessions: create, inspect, discard.

Thin transport over :class:`SessionStore`. The ids are issued HERE and never
accepted from the client: an id the service did not mint is an id it cannot
validate, and it lets two browser tabs share a conversation by accident.

|| Sesiones de conversación: crear, inspeccionar, descartar. Transporte
delgado sobre :class:`SessionStore`. Los ids se emiten ACÁ y nunca se aceptan
del cliente: un id que el servicio no acuñó es un id que no puede validar, y
deja que dos pestañas compartan una conversación por accidente.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.foundation.persistence.database import get_async_session
from app.generation.conversation.models import AnchorKind, ConversationFacts
from app.generation.conversation.store import SessionStore

router = APIRouter(prefix="/answer/session", tags=["answer-session"])
log = structlog.get_logger()


class SessionCreated(BaseModel):
    """A fresh conversation. || Una conversación nueva."""

    session_id: str = Field(
        description="Send this as `session_id` on every turn. "
        "|| Mandar esto como `session_id` en cada turno."
    )


class AnchorView(BaseModel):
    """A pinned constraint, and the question that pinned it.

    || Una restricción fijada, y la pregunta que la fijó.
    """

    kind: AnchorKind
    value: str
    source_question: str


class TurnView(BaseModel):
    """One remembered exchange. || Un intercambio recordado."""

    question: str
    resolved_question: str
    answer: str


class SessionView(BaseModel):
    """What the session currently remembers. || Lo que la sesión recuerda hoy."""

    session_id: str
    facts: ConversationFacts
    anchors: list[AnchorView] = Field(default_factory=list)
    turns: list[TurnView] = Field(default_factory=list)
    max_turns: int = Field(
        description="Window size the service trims to. || Tamaño de ventana al que recorta."
    )


def _store(session: AsyncSession) -> SessionStore:
    return SessionStore(session, ttl_days=get_settings().CONVERSATION_SESSION_TTL_DAYS)


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
) -> SessionCreated:
    """Start a conversation. || Arranca una conversación."""
    conversation = await _store(session).create()
    return SessionCreated(session_id=conversation.session_id)


@router.get("/{session_id}", response_model=SessionView)
async def read_session(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
) -> SessionView:
    """What this conversation remembers. || Lo que recuerda esta conversación."""
    conversation = await _store(session).get(session_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired session_id. || session_id desconocido o vencido.",
        )
    return SessionView(
        session_id=conversation.session_id,
        facts=conversation.facts,
        anchors=[
            AnchorView(
                kind=anchor.kind,
                value=anchor.value,
                source_question=anchor.source_question,
            )
            for anchor in conversation.anchors
        ],
        turns=[
            TurnView(
                question=turn.question,
                resolved_question=turn.resolved_question,
                answer=turn.answer,
            )
            for turn in conversation.turns
        ],
        max_turns=get_settings().CONVERSATION_MAX_TURNS,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
) -> None:
    """Discard a conversation.

    Idempotent: deleting a session that is already gone is the outcome the
    caller wanted, not an error. "Start a new thread" must not be able to
    fail because the previous thread had already expired.

    || Descarta una conversación. Idempotente: borrar una sesión que ya no
    está es el resultado que quería quien llama, no un error. «Empezar un hilo
    nuevo» no puede fallar porque el hilo anterior ya hubiera vencido.
    """
    await _store(session).delete(session_id)


@router.delete("/{session_id}/anchors/{kind}/{value}", response_model=SessionView)
async def unpin_anchor(
    session_id: str,
    kind: AnchorKind,
    value: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
) -> SessionView:
    """Remove one pinned constraint. || Quita una restricción fijada."""
    store = _store(session)
    conversation = await store.get(session_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or expired session_id. || session_id desconocido o vencido.",
        )
    if conversation.unpin(kind, value):
        await store.save(conversation)
    return await read_session(session_id, session)
