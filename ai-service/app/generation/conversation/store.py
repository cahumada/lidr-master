"""Sessions in Postgres, one row per conversation.

The course keeps its sessions in the FastAPI process and says so: state is
lost on restart, which is right for an exercise. It is wrong here. The
console is a web app with reloads, tabs and deploys, and a session that dies
on every restart produces the same symptom this change exists to remove, only
intermittently. Postgres and alembic are already in the stack, so there is no
new infrastructure to justify.

Not the LangGraph checkpointer either, which is the other tempting home. A
``thread_id`` is ONE run of the graph, with its own human-review pause; a
session spans many runs. Storing session memory in the checkpointer would
make resuming a paused thread revive facts from a turn that already closed —
and those tables are deliberately excluded from alembic's autogenerate
(``include_name`` in ``env.py``), so they are not ours to extend.

JSONB and not columns, which is the opposite of the call made in
``rag/store/models.py`` — and for the same reason. There, the metadata has
fixed fields and every one of them is filtered, so columns give indexes,
statistics and a SQL error on a typo. Here, turns and anchors are
variable-length nested lists and nothing ever queries inside them: a session
is fetched whole, by id. Columns would buy nothing and cost a migration per
field.

|| Sesiones en Postgres, una fila por conversación.

El curso las guarda en memoria del proceso y lo dice: el estado se pierde al
reiniciar, correcto para un ejercicio. Acá no: la consola es una app web con
recargas, pestañas y deploys, y una sesión que muere en cada reinicio produce
el mismo síntoma que este cambio viene a sacar, de forma intermitente.

Tampoco el checkpointer de LangGraph: un ``thread_id`` es UNA corrida del
grafo, una sesión son muchas, y esas tablas están excluidas de alembic a
propósito.

JSONB y no columnas, al revés que en ``rag/store/models.py`` y por la misma
razón: allá los campos son fijos y todos se filtran; acá los turnos y anchors
son listas anidadas de largo variable y nunca se consulta adentro — una sesión
se lee entera, por id.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import DateTime, String, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.foundation.persistence.database import Base
from app.generation.conversation.models import (
    Anchor,
    ConversationFacts,
    ConversationSession,
    HistoryTurn,
    Turn,
)

log = structlog.get_logger()


class ConversationSessionRow(Base):
    """One conversation. || Una conversación."""

    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    anchors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    turns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def _to_domain(row: ConversationSessionRow) -> ConversationSession:
    return ConversationSession(
        session_id=row.id,
        title=row.title,
        facts=ConversationFacts.model_validate(row.facts or {}),
        anchors=[Anchor.model_validate(item) for item in (row.anchors or [])],
        turns=[Turn.model_validate(item) for item in (row.turns or [])],
        history=[HistoryTurn.model_validate(item) for item in (row.history or [])],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SessionStore:
    """Read and write conversations. || Lee y escribe conversaciones."""

    def __init__(self, session: AsyncSession, *, ttl_days: int) -> None:
        self._session = session
        self._ttl_days = ttl_days

    async def create(self) -> ConversationSession:
        """Start an empty conversation. || Arranca una conversación vacía."""
        conversation = ConversationSession()
        self._session.add(
            ConversationSessionRow(
                id=conversation.session_id,
                facts={},
                anchors=[],
                turns=[],
                history=[],
                title=None,
            )
        )
        await self._session.commit()
        log.info("conversation_session_created", session_id=conversation.session_id)
        return conversation

    async def get(self, session_id: str) -> ConversationSession | None:
        """The conversation, or ``None`` when it is missing OR expired.

        Expiry is deliberately indistinguishable from absence at this level.
        The caller answers the turn without memory and says so; raising a 404
        in the middle of a conversation would turn a housekeeping detail into
        a dead end for the user.

        || La conversación, o ``None`` si no existe O venció. El vencimiento
        se hace indistinguible de la ausencia a propósito: quien llama
        responde el turno sin memoria y lo dice, en vez de cortarle la
        conversación al usuario por un detalle de mantenimiento.
        """
        row = await self._session.get(ConversationSessionRow, session_id)
        if row is None:
            return None
        cutoff = datetime.now(UTC) - timedelta(days=self._ttl_days)
        if row.updated_at < cutoff:
            log.info("conversation_session_expired", session_id=session_id)
            return None
        return _to_domain(row)

    async def save(self, conversation: ConversationSession) -> None:
        """Persist the whole conversation. || Persiste la conversación entera."""
        row = await self._session.get(ConversationSessionRow, conversation.session_id)
        if row is None:
            row = ConversationSessionRow(id=conversation.session_id)
            self._session.add(row)
        row.title = conversation.title
        row.facts = conversation.facts.model_dump(mode="json")
        row.anchors = [anchor.model_dump(mode="json") for anchor in conversation.anchors]
        row.turns = [turn.model_dump(mode="json") for turn in conversation.turns]
        row.history = [turn.model_dump(mode="json") for turn in conversation.history]
        await self._session.commit()

    async def list_recent(self, *, limit: int, offset: int) -> list[ConversationSession]:
        """Summaries the operator can reopen: not empty, not expired, newest first.

        || Las que el operador puede reabrir: no vacías, no vencidas, la más
        reciente primero.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._ttl_days)
        result = await self._session.execute(
            select(ConversationSessionRow)
            .where(
                ConversationSessionRow.updated_at >= cutoff,
                func.jsonb_array_length(ConversationSessionRow.history) > 0,
            )
            .order_by(ConversationSessionRow.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def rename(self, session_id: str, title: str) -> ConversationSession | None:
        """Set the title, or ``None`` when the session is missing or expired.

        || Pone el título, o ``None`` si la sesión no existe o venció.
        """
        conversation = await self.get(session_id)
        if conversation is None:
            return None
        conversation.title = title
        await self.save(conversation)
        log.info("conversation_session_renamed", session_id=session_id)
        return await self.get(session_id)

    async def delete(self, session_id: str) -> bool:
        """Drop a conversation. || Borra una conversación."""
        result = await self._session.execute(
            delete(ConversationSessionRow).where(ConversationSessionRow.id == session_id)
        )
        await self._session.commit()
        deleted = bool(result.rowcount)
        if deleted:
            log.info("conversation_session_deleted", session_id=session_id)
        return deleted

    async def purge_expired(self) -> int:
        """Remove rows past the TTL. || Saca las filas que pasaron el TTL."""
        cutoff = datetime.now(UTC) - timedelta(days=self._ttl_days)
        result = await self._session.execute(
            delete(ConversationSessionRow).where(ConversationSessionRow.updated_at < cutoff)
        )
        await self._session.commit()
        return int(result.rowcount or 0)

    async def count(self) -> int:
        """How many conversations are stored. || Cuántas conversaciones hay."""
        result = await self._session.execute(
            select(func.count()).select_from(ConversationSessionRow)
        )
        return int(result.scalar_one())
