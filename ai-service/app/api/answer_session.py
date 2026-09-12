"""Conversation sessions: create, inspect, list, rename, discard.

Thin transport over :class:`SessionStore`. The ids are issued HERE and never
accepted from the client: an id the service did not mint is an id it cannot
validate, and it lets two browser tabs share a conversation by accident.

``GET /answer/sessions`` is registered on a sibling router so ``sessions``
cannot be captured as a ``session_id``.

|| Sesiones de conversación: crear, inspeccionar, listar, renombrar, descartar.
Transporte delgado sobre :class:`SessionStore`. Los ids se emiten ACÁ y nunca
se aceptan del cliente.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import resolve_console_user
from app.foundation.persistence.database import get_async_session
from app.generation.conversation.models import (
    AnchorKind,
    ConversationFacts,
    ConversationSession,
)
from app.generation.conversation.store import SessionStore

router = APIRouter(prefix="/answer/session", tags=["answer-session"])
list_router = APIRouter(prefix="/answer/sessions", tags=["answer-session"])
log = structlog.get_logger()

_UNKNOWN = "Unknown or expired session_id. || session_id desconocido o vencido."


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
    """One remembered exchange (memory window). || Un intercambio de la ventana."""

    question: str
    resolved_question: str
    answer: str


class CitationSnapshotView(BaseModel):
    """What a closed turn cited, without chunk text.

    || Lo que un turno cerrado citó, sin el texto del chunk.
    """

    document_id: str
    document_title: str | None = None
    section: str | None = None
    bullet_path: str | None = None
    content_hash: str = ""


class HistoryTurnView(BaseModel):
    """One closed exchange as the operator should see it again.

    || Un intercambio cerrado como el operador debería volver a verlo.
    """

    question: str
    resolved_question: str
    answer: str
    citations: list[CitationSnapshotView] = Field(default_factory=list)
    grounded: bool = True
    created_at: datetime


class SessionView(BaseModel):
    """Memory slots plus the durable transcript. || Memoria más el transcript."""

    session_id: str
    title: str | None = None
    facts: ConversationFacts
    anchors: list[AnchorView] = Field(default_factory=list)
    turns: list[TurnView] = Field(default_factory=list)
    history: list[HistoryTurnView] = Field(default_factory=list)
    max_turns: int = Field(
        description="Window size the service trims to. || Tamaño de ventana al que recorta."
    )
    created_at: datetime
    updated_at: datetime


class SessionSummary(BaseModel):
    """One row of the conversation list. || Una fila del listado."""

    session_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    turn_count: int


class SessionRename(BaseModel):
    """New title for a live session. || Título nuevo de una sesión viva."""

    title: str = Field(
        min_length=1,
        description="Replacement title. Cannot be blank. "
        "|| Título de reemplazo. No puede quedar vacío.",
    )

    @field_validator("title")
    @classmethod
    def collapse_and_cap(cls, value: str) -> str:
        collapsed = " ".join(value.split())
        max_chars = get_settings().CONVERSATION_TITLE_MAX_CHARS
        if not collapsed:
            raise ValueError("title must not be empty || el título no puede estar vacío")
        if len(collapsed) > max_chars:
            raise ValueError(
                f"title must be at most {max_chars} characters "
                f"|| el título no puede superar {max_chars} caracteres"
            )
        return collapsed


def _store(session: AsyncSession, owner_id: str | None) -> SessionStore:
    """The store scoped to whoever is asking.

    ``owner_id`` is positional and has no default on purpose: a route added
    tomorrow cannot forget it, because forgetting it does not compile.

    || El store acotado a quien pregunta. ``owner_id`` es posicional y sin
    default a propósito: una ruta nueva no puede olvidarlo, porque olvidarlo
    no compila.
    """
    return SessionStore(
        session,
        ttl_days=get_settings().CONVERSATION_SESSION_TTL_DAYS,
        owner_id=owner_id,
    )


def _to_view(conversation: ConversationSession) -> SessionView:
    return SessionView(
        session_id=conversation.session_id,
        title=conversation.title,
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
        history=[
            HistoryTurnView(
                question=turn.question,
                resolved_question=turn.resolved_question,
                answer=turn.answer,
                citations=[
                    CitationSnapshotView(
                        document_id=citation.document_id,
                        document_title=citation.document_title,
                        section=citation.section,
                        bullet_path=citation.bullet_path,
                        content_hash=citation.content_hash,
                    )
                    for citation in turn.citations
                ],
                grounded=turn.grounded,
                created_at=turn.created_at,
            )
            for turn in conversation.history
        ],
        max_turns=get_settings().CONVERSATION_MAX_TURNS,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
    owner_id: str | None = Depends(resolve_console_user),
) -> SessionCreated:
    """Start a conversation. || Arranca una conversación."""
    conversation = await _store(session, owner_id).create()
    return SessionCreated(session_id=conversation.session_id)


@list_router.get("", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
    owner_id: str | None = Depends(resolve_console_user),
) -> list[SessionSummary]:
    """The caller's own conversations, the ones they can reopen.

    Not the tenant's. The caller arrives in ``X-Console-User``, which only the
    BFF can send. A request without it sees the conversations that have no
    owner either — absence of identity is its own bucket and never a wildcard.

    || Las conversaciones propias de quien llama, las que puede reabrir. No las
    del tenant. Quien llama viaja en ``X-Console-User``, que solo el BFF puede
    mandar. Un request sin ese header ve las que tampoco tienen dueño.
    """
    conversations = await _store(session, owner_id).list_recent(limit=limit, offset=offset)
    return [
        SessionSummary(
            session_id=item.session_id,
            title=item.title,
            created_at=item.created_at,
            updated_at=item.updated_at,
            turn_count=len(item.history),
        )
        for item in conversations
    ]


@router.get("/{session_id}", response_model=SessionView)
async def read_session(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
    owner_id: str | None = Depends(resolve_console_user),
) -> SessionView:
    """What this conversation remembers, and its transcript.

    || Lo que recuerda esta conversación, y su transcript.
    """
    conversation = await _store(session, owner_id).get(session_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_UNKNOWN)
    return _to_view(conversation)


@router.patch("/{session_id}", response_model=SessionView)
async def rename_session(
    session_id: str,
    body: SessionRename,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
    owner_id: str | None = Depends(resolve_console_user),
) -> SessionView:
    """Rename a live session. || Renombra una sesión viva."""
    conversation = await _store(session, owner_id).rename(session_id, body.title)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_UNKNOWN)
    return _to_view(conversation)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
    owner_id: str | None = Depends(resolve_console_user),
) -> None:
    """Discard a conversation.

    Idempotent: deleting a session that is already gone is the outcome the
    caller wanted, not an error. "Start a new thread" must not be able to
    fail because the previous thread had already expired.

    || Descarta una conversación. Idempotente: borrar una sesión que ya no
    está es el resultado que quería quien llama, no un error. «Empezar un hilo
    nuevo» no puede fallar porque el hilo anterior ya hubiera vencido.
    """
    await _store(session, owner_id).delete(session_id)


@router.delete("/{session_id}/anchors/{kind}/{value}", response_model=SessionView)
async def unpin_anchor(
    session_id: str,
    kind: AnchorKind,
    value: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 - FastAPI's required DI idiom.
    owner_id: str | None = Depends(resolve_console_user),
) -> SessionView:
    """Remove one pinned constraint. || Quita una restricción fijada."""
    store = _store(session, owner_id)
    conversation = await store.get(session_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_UNKNOWN)
    if conversation.unpin(kind, value):
        await store.save(conversation)
    # The owner is passed explicitly: calling the handler as a plain function
    # bypasses FastAPI, so an omitted argument would arrive as the `Depends`
    # object itself and match no owner at all.
    # || El dueño va explícito: llamar al handler como función común saltea a
    # FastAPI, así que un argumento omitido llegaría como el propio `Depends`
    # y no matchearía con ningún dueño.
    return await read_session(session_id, session, owner_id)
