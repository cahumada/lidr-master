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
from sqlalchemy import DateTime, Index, String, delete, func, select
from sqlalchemy import text as sa_text
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
    # Composite and not one index per column: every read is "this owner's, by
    # recency", so the pair is what the planner can actually use. A lone index
    # on ``owner_id`` would be a second structure covering a prefix of this one.
    # || Compuesto y no un índice por columna: toda lectura es «las de este
    # dueño, por recencia».
    __table_args__ = (
        Index(
            "ix_conversation_sessions_owner_updated",
            "owner_id",
            sa_text("updated_at DESC"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Who this conversation belongs to: the console's user id, an opaque cuid
    # and never an email. The service compares strings and never learns who
    # anybody is — it does not need PII to resolve this authorization, and not
    # having it is one less leak the day somebody reads the table.
    #
    # Nullable because the rows that already existed have no owner, and an
    # invented owner is worse than none. ``NULL`` is its own bucket, not a
    # wildcard: see ``SessionStore``.
    #
    # || De quién es esta conversación: el id de usuario de la consola, un cuid
    # opaco y nunca un email. El servicio compara cadenas y no aprende quién es
    # nadie. Nullable porque las filas que ya existían no tienen dueño, e
    # inventarles uno es peor que dejarlas sin él.
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
        owner_id=row.owner_id,
        title=row.title,
        facts=ConversationFacts.model_validate(row.facts or {}),
        anchors=[Anchor.model_validate(item) for item in (row.anchors or [])],
        turns=[Turn.model_validate(item) for item in (row.turns or [])],
        history=[HistoryTurn.model_validate(item) for item in (row.history or [])],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SessionStore:
    """Read and write the conversations of ONE owner.

    The owner belongs to the store and not to each method: a method that can be
    called without an owner is a method that will one day be called without one.

    ``owner_id=None`` is not a wildcard — it is the bucket of conversations that
    have no owner either. If absence of identity meant "no filter", the whole
    protection would be turned off by dropping a header, which is the cheapest
    way to not fix anything. It lands correctly on the three callers that
    exist: the console always sends an identity and sees its own; evals and
    scripts send none and see the ownerless ones they create; and somebody
    holding the service token but no identity sees nobody's.

    || Lee y escribe las conversaciones de UN dueño. El dueño es del store y no
    de cada método: un método que pueda llamarse sin dueño es un método que
    algún día se va a llamar sin dueño. ``owner_id=None`` NO es comodín: es el
    balde de las conversaciones que tampoco tienen dueño. Que la ausencia de
    identidad significara «sin filtro» volvería todo esto esquivable quitando
    un header.
    """

    def __init__(
        self, session: AsyncSession, *, ttl_days: int, owner_id: str | None
    ) -> None:
        self._session = session
        self._ttl_days = ttl_days
        self._owner_id = owner_id

    def _owned(self):
        """The ownership predicate, with ``NULL`` matching ``NULL``.

        || El predicado de pertenencia, con ``NULL`` matcheando ``NULL``.
        """
        return ConversationSessionRow.owner_id.is_not_distinct_from(self._owner_id)

    async def create(self) -> ConversationSession:
        """Start an empty conversation. || Arranca una conversación vacía."""
        conversation = ConversationSession(owner_id=self._owner_id)
        self._session.add(
            ConversationSessionRow(
                id=conversation.session_id,
                owner_id=self._owner_id,
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
        """The conversation, or ``None`` when it is missing, expired OR not ours.

        The third case joins the first two on purpose. Telling them apart would
        say "this id exists, but not for you", which is information about
        another person's activity; the router already answers 404 for the other
        two, and this is the third face of the same indistinguishability.

        || La conversación, o ``None`` si no existe, venció O no es nuestra. El
        tercer caso se suma a los otros dos a propósito: distinguirlos diría
        «este id existe, pero no es tuyo», que es información sobre la
        actividad de otra persona.

        Expiry is deliberately indistinguishable from absence at this level.
        The caller answers the turn without memory and says so; raising a 404
        in the middle of a conversation would turn a housekeeping detail into
        a dead end for the user.

        || La conversación, o ``None`` si no existe O venció. El vencimiento
        se hace indistinguible de la ausencia a propósito: quien llama
        responde el turno sin memoria y lo dice, en vez de cortarle la
        conversación al usuario por un detalle de mantenimiento.
        """
        result = await self._session.execute(
            select(ConversationSessionRow).where(
                ConversationSessionRow.id == session_id, self._owned()
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        cutoff = datetime.now(UTC) - timedelta(days=self._ttl_days)
        if row.updated_at < cutoff:
            log.info("conversation_session_expired", session_id=session_id)
            return None
        return _to_domain(row)

    async def save(self, conversation: ConversationSession) -> None:
        """Persist the whole conversation. || Persiste la conversación entera."""
        result = await self._session.execute(
            select(ConversationSessionRow).where(
                ConversationSessionRow.id == conversation.session_id, self._owned()
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            # Either it never existed, or it belongs to somebody else. Creating
            # it here with OUR owner is right for the first case and impossible
            # for the second: a row that already exists under another owner
            # collides on the primary key instead of quietly changing hands.
            # || O no existía, o es de otra persona. Crearla acá con NUESTRO
            # dueño es lo correcto en el primer caso e imposible en el segundo:
            # una fila que ya existe con otro dueño choca contra la PK en vez
            # de cambiar de manos en silencio.
            row = ConversationSessionRow(
                id=conversation.session_id, owner_id=self._owner_id
            )
            self._session.add(row)
        row.title = conversation.title
        row.facts = conversation.facts.model_dump(mode="json")
        row.anchors = [anchor.model_dump(mode="json") for anchor in conversation.anchors]
        row.turns = [turn.model_dump(mode="json") for turn in conversation.turns]
        row.history = [turn.model_dump(mode="json") for turn in conversation.history]
        await self._session.commit()

    async def list_recent(self, *, limit: int, offset: int) -> list[ConversationSession]:
        """The owner's own: not empty, not expired, newest first.

        The owner filter lives in the ``WHERE`` and is never applied to rows
        already read. Filtering afterwards works until somebody pages: with a
        ``limit``, reading 50 and discarding the foreign ones returns short
        pages and a last page that lies — and a foreign row that is read and
        thrown away already crossed the network and the logs.

        || Las del dueño: no vacías, no vencidas, la más reciente primero. El
        filtro va en el ``WHERE`` y nunca sobre lo ya leído: filtrar después
        funciona hasta el día que alguien pagina.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._ttl_days)
        result = await self._session.execute(
            select(ConversationSessionRow)
            .where(
                self._owned(),
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
            delete(ConversationSessionRow).where(
                ConversationSessionRow.id == session_id, self._owned()
            )
        )
        await self._session.commit()
        deleted = bool(result.rowcount)
        if deleted:
            log.info("conversation_session_deleted", session_id=session_id)
        return deleted

    async def purge_expired(self) -> int:
        """Remove rows past the TTL, of every owner.

        Deliberately NOT scoped to the store's owner: expiring is the clock's
        business, not the caller's, and a sweep that only reached the rows of
        whoever happened to call it would leave everybody else's forever.

        || Saca las filas que pasaron el TTL, de todos los dueños. A propósito
        NO se acota al dueño del store: vencer es del reloj, no de quien
        pregunta.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._ttl_days)
        result = await self._session.execute(
            delete(ConversationSessionRow).where(ConversationSessionRow.updated_at < cutoff)
        )
        await self._session.commit()
        return int(result.rowcount or 0)

    async def count(self) -> int:
        """How many conversations this owner has. || Cuántas tiene este dueño."""
        result = await self._session.execute(
            select(func.count()).select_from(ConversationSessionRow).where(self._owned())
        )
        return int(result.scalar_one())
