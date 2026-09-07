"""GET /usage/summary — tenant-wide chat-completion totals.

Thin transport: the store aggregates. The tenant comes from settings, never
from the query string.

|| GET /usage/summary — totales de chat del tenant. Transporte delgado: el
store agrega. El tenant sale de settings, nunca del query.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.foundation.persistence.database import get_async_session
from app.foundation.persistence.usage import UsageStore

router = APIRouter(prefix="/usage", tags=["usage"])

UsagePurposeQuery = Literal["answer", "answer_synthesizer"]


class UsageByModel(BaseModel):
    """Totals for one provider + model. || Totales de un proveedor + modelo."""

    provider_id: str
    model: str
    calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class UsageSummary(BaseModel):
    """Tenant aggregate. || Agregado del tenant."""

    total_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    by_model: list[UsageByModel] = Field(default_factory=list)


def _store(session: AsyncSession) -> UsageStore:
    return UsageStore(session)


@router.get("/summary", response_model=UsageSummary)
async def usage_summary(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
    since: datetime | None = Query(default=None, alias="from"),  # noqa: B008
    until: datetime | None = Query(default=None, alias="to"),  # noqa: B008
    session_id: str | None = None,
    purpose: UsagePurposeQuery | None = None,
) -> UsageSummary:
    """Totals for this deployment's tenant. || Totales del tenant de este despliegue."""
    if since is not None and until is not None and since > until:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="`from` must not be later than `to`. || `from` no puede ser posterior a `to`.",
        )
    totals = await _store(session).summarize(
        get_settings().TENANT_ID,
        since=since,
        until=until,
        session_id=session_id,
        purpose=purpose,
    )
    return UsageSummary(
        total_calls=totals.total_calls,
        input_tokens=totals.input_tokens,
        output_tokens=totals.output_tokens,
        total_tokens=totals.total_tokens,
        by_model=[
            UsageByModel(
                provider_id=item.provider_id,
                model=item.model,
                calls=item.calls,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                total_tokens=item.total_tokens,
            )
            for item in totals.by_model
        ],
    )
