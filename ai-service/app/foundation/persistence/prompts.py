"""What was actually sent to the model, kept for a short window.

The synthesis prompt is not reconstructible after the fact: persona, guardrails,
the synthesizer profile, session memory, the active mirror run and the budget
trims all move between the answer and the moment someone looks at it. A
re-render would show a prompt that was never sent, presented as if it had been —
the same defect `business-db-context` avoids by dating validity with the run's
`created_at_utc` instead of `now()`. So the text is stored at send time or it is
gone.

It is stored in its own table and NOT on `llm_usage_events`: that one is
accounting, small and permanent, read by `/usage`. Hanging 60 KB of text off it
would change its growth profile and force a 7-day retention onto a capability
that does not want one.

|| Lo que realmente se le mandó al modelo, guardado por una ventana corta. El
prompt no se puede reconstruir después, así que se guarda al enviarlo o se
pierde. Va en su propia tabla y no en `llm_usage_events`, que es contabilidad.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import structlog
from sqlalchemy import DateTime, Index, Integer, String, Text, delete, func, select
from sqlalchemy.orm import Mapped, mapped_column

from app.foundation.persistence.database import Base, get_session_factory

log = structlog.get_logger()


class AnswerPromptRow(Base):
    """One synthesis prompt, exactly as it went to the provider.

    || Un prompt de síntesis, tal como salió hacia el proveedor.
    """

    __tablename__ = "answer_prompts"
    __table_args__ = (
        # The retention sweep walks this. Without it, every write would scan
        # the table -- and the table is the one holding 60 KB rows.
        # || Por acá barre la retención. Sin el índice, cada escritura
        # recorrería la tabla, que es justo la de las filas de 60 KB.
        Index("ix_answer_prompts_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Which agent composed it. Today only the synthesizer writes here; the
    # column exists so auditing another one later does not need a migration.
    # || Qué agente lo compuso. Hoy solo escribe el sintetizador.
    agent: Mapped[str] = mapped_column(String(48), nullable=False)

    model: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The two halves, verbatim. Not markdown, not trimmed: a prompt is audited
    # for what it literally says.
    # || Las dos mitades, literales.
    system_text: Mapped[str] = mapped_column(Text, nullable=False)
    user_text: Mapped[str] = mapped_column(Text, nullable=False)

    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


@dataclass(frozen=True)
class StoredPrompt:
    """A prompt read back, as the endpoint needs it.

    || Un prompt leído, como lo necesita el endpoint.
    """

    id: str
    created_at: datetime
    agent: str
    model: str
    profile_id: str | None
    context_budget: int
    system_text: str
    user_text: str


def _cutoff(retention_days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=max(retention_days, 0))


def save_prompt(
    *,
    tenant_id: str,
    agent: str,
    model: str,
    system_text: str,
    user_text: str,
    context_budget: int,
    retention_days: int,
    profile_id: str | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    session_factory=None,
) -> str | None:
    """Store one prompt, sweep what expired, and return the id — or ``None``.

    The sweep rides along with the INSERT on purpose. A cron would be tidier
    and has a concrete failure mode: nobody configures it, and the table grows
    in silence holding the most sensitive material the service handles. A
    retention policy that depends on a manual step is a policy that does not
    exist.

    Returns ``None`` instead of raising when anything fails. This runs right
    after a 40-50s completion the user is waiting on: losing the audit trail is
    a bad turn, losing the answer is a broken one.

    || Guarda un prompt, barre lo vencido y devuelve el id — o ``None``. El
    barrido viaja con el INSERT a propósito: un cron que nadie configura deja
    crecer la tabla en silencio. Devuelve ``None`` en vez de propagar: perder
    la auditoría es un turno malo, perder la respuesta es un turno roto.
    """
    prompt_id = str(uuid4())
    row = AnswerPromptRow(
        id=prompt_id,
        tenant_id=tenant_id,
        agent=agent,
        model=model,
        profile_id=profile_id,
        context_budget=context_budget,
        system_text=system_text,
        user_text=user_text,
        thread_id=thread_id,
        session_id=session_id,
    )
    factory = session_factory or get_session_factory()
    try:
        with factory() as session:
            session.add(row)
            session.execute(
                delete(AnswerPromptRow)
                .where(AnswerPromptRow.tenant_id == tenant_id)
                .where(AnswerPromptRow.created_at < _cutoff(retention_days))
            )
            session.commit()
    except Exception as error:  # noqa: BLE001 — the answer outranks its audit trail.
        log.warning("answer_prompt_not_stored", error=str(error), agent=agent)
        return None
    return prompt_id


def read_prompt(
    prompt_id: str,
    *,
    tenant_id: str,
    retention_days: int,
    session_factory=None,
) -> StoredPrompt | None:
    """One prompt by id, or ``None`` when it is absent or past the window.

    The window is re-checked on READ and not trusted to the sweep: a row that
    outlived a sweep which did not run is still expired, and serving it would
    make the retention promise depend on write traffic.

    || Un prompt por id, o ``None`` si no está o pasó la ventana. La ventana se
    vuelve a chequear en la LECTURA: una fila que sobrevivió a un barrido que no
    corrió igual está vencida.
    """
    factory = session_factory or get_session_factory()
    with factory() as session:
        row = session.execute(
            select(AnswerPromptRow)
            .where(AnswerPromptRow.id == prompt_id)
            .where(AnswerPromptRow.tenant_id == tenant_id)
            .where(AnswerPromptRow.created_at >= _cutoff(retention_days))
        ).scalar_one_or_none()
        if row is None:
            return None
        return StoredPrompt(
            id=row.id,
            created_at=row.created_at,
            agent=row.agent,
            model=row.model,
            profile_id=row.profile_id,
            context_budget=row.context_budget,
            system_text=row.system_text,
            user_text=row.user_text,
        )
