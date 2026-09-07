"""Ledger of chat-completion token usage.

The adapters extract ``Usage``; this module is the consumer that persists
it. Writes happen at the ``complete()`` call — a later human-review reject
does not un-bill the provider — so ``record`` is synchronous and uses its
own short-lived session. ``summarize`` stays on the async query path.

|| Ledger del uso de tokens de chat. Los adaptadores extraen ``Usage``; este
módulo es el consumidor que lo persiste. La escritura ocurre en el
``complete()`` — un reject posterior no des-cobra al proveedor — así que
``record`` es síncrono y abre su propia sesión corta.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import uuid4

import structlog
from sqlalchemy import Boolean, DateTime, Index, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.foundation.llm.wrapper import LLM, Completion, Usage
from app.foundation.persistence.database import Base, get_session_factory

log = structlog.get_logger()

UsagePurpose = Literal["answer", "answer_synthesizer"]

PURPOSE_ANSWER: UsagePurpose = "answer"
PURPOSE_SYNTHESIZER: UsagePurpose = "answer_synthesizer"


class LlmUsageEventRow(Base):
    """One billed chat completion. || Una completion de chat cobrada."""

    __tablename__ = "llm_usage_events"
    __table_args__ = (
        Index("ix_llm_usage_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_llm_usage_events_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    reported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


@dataclass(frozen=True)
class UsageByModel:
    """Totals for one provider + model. || Totales de un proveedor + modelo."""

    provider_id: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class UsageTotals:
    """Tenant-wide aggregate. || Agregado del tenant."""

    total_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    by_model: list[UsageByModel]


class UsageStore:
    """Insert one event; aggregate many. || Inserta un evento; agrega muchos."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        sync_session_factory: Callable[[], Session] | sessionmaker[Session] | None = None,
    ) -> None:
        self._session = session
        self._sync_session_factory = sync_session_factory

    def record(
        self,
        *,
        tenant_id: str,
        purpose: str,
        provider_id: str,
        model: str,
        usage: Usage,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> None:
        """Insert one row and commit. Called from sync ``complete()``.

        A dedicated sync transaction, not the request session: adding to the
        request session and hoping it commits would lose the row if that
        request later rolled back — and the provider already billed us.

        || Inserta una fila y commitea. Una transacción sync propia, no la
        sesión del request: si esa sesión después hace rollback, el
        proveedor igual ya cobró.
        """
        row = LlmUsageEventRow(
            id=str(uuid4()),
            tenant_id=tenant_id,
            purpose=purpose,
            provider_id=provider_id,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            reported=usage.reported,
            session_id=session_id,
            thread_id=thread_id,
        )
        factory = self._sync_session_factory or get_session_factory()
        with factory() as session:
            session.add(row)
            session.commit()

    async def summarize(
        self,
        tenant_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        session_id: str | None = None,
        purpose: str | None = None,
    ) -> UsageTotals:
        """Aggregate the tenant's ledger. Empty window → zeros, not an error.

        || Agrega el ledger del tenant. Ventana vacía → ceros, no un error.
        """
        if self._session is None:
            raise RuntimeError("UsageStore.summarize requires an async session")

        filters = [LlmUsageEventRow.tenant_id == tenant_id]
        if since is not None:
            filters.append(LlmUsageEventRow.created_at >= since)
        if until is not None:
            filters.append(LlmUsageEventRow.created_at <= until)
        if session_id is not None:
            filters.append(LlmUsageEventRow.session_id == session_id)
        if purpose is not None:
            filters.append(LlmUsageEventRow.purpose == purpose)

        stmt = (
            select(
                LlmUsageEventRow.provider_id,
                LlmUsageEventRow.model,
                func.count().label("calls"),
                func.coalesce(func.sum(LlmUsageEventRow.input_tokens), 0).label(
                    "input_tokens"
                ),
                func.coalesce(func.sum(LlmUsageEventRow.output_tokens), 0).label(
                    "output_tokens"
                ),
                func.coalesce(func.sum(LlmUsageEventRow.total_tokens), 0).label(
                    "total_tokens"
                ),
            )
            .where(*filters)
            .group_by(LlmUsageEventRow.provider_id, LlmUsageEventRow.model)
            .order_by(LlmUsageEventRow.provider_id, LlmUsageEventRow.model)
        )
        rows = (await self._session.execute(stmt)).all()
        by_model = [
            UsageByModel(
                provider_id=row.provider_id,
                model=row.model,
                calls=int(row.calls),
                input_tokens=int(row.input_tokens),
                output_tokens=int(row.output_tokens),
                total_tokens=int(row.total_tokens),
            )
            for row in rows
        ]
        return UsageTotals(
            total_calls=sum(item.calls for item in by_model),
            input_tokens=sum(item.input_tokens for item in by_model),
            output_tokens=sum(item.output_tokens for item in by_model),
            total_tokens=sum(item.total_tokens for item in by_model),
            by_model=by_model,
        )


class RecordingLLM:
    """An ``LLM`` that writes a ledger row after each successful completion.

    || Un ``LLM`` que escribe una fila del ledger después de cada completion
    exitosa.
    """

    def __init__(
        self,
        inner: LLM,
        store: UsageStore,
        *,
        purpose: str,
        provider_id: str,
        tenant_id: str,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> None:
        self._inner = inner
        self._store = store
        self.model = inner.model
        self._purpose = purpose
        self._provider_id = provider_id
        self._tenant_id = tenant_id
        self._session_id = session_id
        self._thread_id = thread_id

    def complete(self, *, system: str, user: str) -> Completion:
        """Delegate, then persist. A store failure does not hide the text.

        || Delega y después persiste. Una falla del store no esconde el texto.
        """
        completion = self._inner.complete(system=system, user=user)
        try:
            self._store.record(
                tenant_id=self._tenant_id,
                purpose=self._purpose,
                provider_id=self._provider_id,
                model=self.model,
                usage=completion.usage,
                session_id=self._session_id,
                thread_id=self._thread_id,
            )
        except Exception:
            log.exception(
                "llm_usage_record_failed",
                purpose=self._purpose,
                provider_id=self._provider_id,
                model=self.model,
            )
        return completion


def llm_with_accounting(
    llm: LLM,
    *,
    purpose: str,
    provider_id: str,
    tenant_id: str,
    session_id: str | None = None,
    thread_id: str | None = None,
    store: UsageStore | None = None,
) -> RecordingLLM:
    """Wrap ``llm`` so each successful ``complete()`` writes a ledger row.

    || Envuelve ``llm`` para que cada ``complete()`` exitoso escriba una fila.
    """
    return RecordingLLM(
        llm,
        store or UsageStore(),
        purpose=purpose,
        provider_id=provider_id,
        tenant_id=tenant_id,
        session_id=session_id,
        thread_id=thread_id,
    )


__all__ = [
    "PURPOSE_ANSWER",
    "PURPOSE_SYNTHESIZER",
    "LlmUsageEventRow",
    "RecordingLLM",
    "UsageByModel",
    "UsagePurpose",
    "UsageStore",
    "UsageTotals",
    "llm_with_accounting",
]
