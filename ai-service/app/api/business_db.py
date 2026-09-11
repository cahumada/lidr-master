"""Which mirror run the service reads from: list them, activate one.

Thin transport. The store decides; this file turns its refusals into status
codes and its rows into a contract.

Only two verbs, and the asymmetry is deliberate: the mirror is read-only from
here — `visualtime.*` is written by `dw-oracle-extractor` — so there is nothing
to create or delete. What this router writes is OUR selection.

|| Con qué corrida del mirror lee el servicio: listarlas, activar una.
Transporte delgado: el store decide, y acá se traducen sus rechazos a códigos y
sus filas a un contrato. Dos verbos y nada más, a propósito: el mirror es de
solo lectura desde acá, así que no hay nada que crear ni borrar. Lo que este
router escribe es NUESTRA selección.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.business_db_store import (
    ActiveRun,
    MirrorRun,
    RunNotLoaded,
    RunOrigin,
    TableBuild,
    activate_run,
    find_mirror_run,
    get_stamp,
    list_mirror_runs,
    list_table_builds,
    resolve_active_run,
)
from app.foundation.persistence.database import get_async_session

router = APIRouter(prefix="/business-db", tags=["business-db"])


class ExtractionRunItem(BaseModel):
    """One run of the mirror, with what a chooser needs to decide.

    The three load flags are independent, so all three travel: only
    ``loaded_data`` gates activation, and the other two tell whoever is
    choosing what that run actually covers.

    || Una corrida del mirror, con lo que hace falta para elegir. Las tres
    banderas viajan: solo ``loaded_data`` condiciona la activación, y las otras
    dos dicen qué cubre esa corrida.
    """

    run_id: str
    env: str
    extractor_version: str | None = None
    created_at_utc: datetime | None = None
    status: str | None = Field(
        default=None,
        description="The extractor's own status for the run. || El estado que le puso el extractor.",
    )
    loaded_metadata: bool
    loaded_dependencies: bool
    loaded_data: bool
    manifest_sha256: str | None = None
    is_active: bool = Field(
        default=False,
        description="Whether this is the run in force. || Si es la corrida en vigor.",
    )
    can_activate: bool = Field(
        description="False when `loaded_data` is false: the navigation tree comes from "
        "`business_data`. || False cuando `loaded_data` es false.",
    )
    tables_built: bool = Field(
        default=False,
        description="Whether the transaction-table edges were built for this run. False "
        "means answers from it carry no tables, and the console warns before activating. "
        "|| Si se construyeron las aristas de tablas por transacción para esta corrida.",
    )
    tables_built_at: datetime | None = Field(
        default=None,
        description="When the batch last ran for this run. || Cuándo corrió el batch.",
    )
    table_edge_count: int = Field(
        default=0,
        description="Edges the batch produced. A build with 0 is still a build. "
        "|| Aristas que produjo el batch. Un build con 0 sigue siendo un build.",
    )


class ActiveRunInfo(BaseModel):
    """The run in force and where it came from.

    ``origin`` is the field that matters. `selected` means somebody chose it;
    `default` means nobody did and `BUSINESS_DB_RUN_ID` supplied it — the seed
    is never written as a row, so this is the only way to tell the two apart.
    `none` means neither, and then ``reason`` says so in words.

    || La corrida en vigor y de dónde salió. ``origin`` es el campo que importa:
    la semilla nunca se escribe como fila, así que es la única forma de
    distinguir «alguien eligió» de «nadie eligió y había un default».
    """

    run_id: str | None = None
    env: str
    origin: RunOrigin
    reason: str | None = None
    activated_at: datetime | None = None
    activated_by: str | None = Field(
        default=None,
        description="DECLARED by the caller, never verified: the service has no user "
        "identity. || DECLARADO por quien llama, nunca verificado.",
    )


class CorpusStampInfo(BaseModel):
    """Which run stamped the corpus metadata, and whether it still matches.

    || Con qué corrida se estampó la metadata del corpus, y si todavía coincide.
    """

    run_id: str
    env: str
    doc_version: str
    stamped_at: datetime
    rows_updated: int = Field(ge=0)
    matches_active: bool = Field(
        description="False means the stamped column is stale relative to the active run. "
        "|| False significa que la columna estampada quedó vieja respecto de la activa.",
    )


class ExtractionRunList(BaseModel):
    """The runs, the one in force, and the corpus stamp beside it.

    The stamp travels with the list so the console can say "stamped with X ·
    active Y" without a second call. That drift is the thing this capability
    exists to make visible.

    || Las corridas, la vigente, y el sello del corpus al lado. El sello viaja
    con la lista para que la consola pueda decir «estampado con X · activa Y»
    sin una segunda llamada: ese desfasaje es lo que esta capability existe para
    hacer visible.
    """

    active: ActiveRunInfo
    stamp: CorpusStampInfo | None = None
    runs: list[ExtractionRunItem] = Field(default_factory=list)


class ActivateRunRequest(BaseModel):
    """Who is activating, as declared by the caller.

    || Quién activa, declarado por quien llama.
    """

    activated_by: str | None = Field(
        default=None,
        max_length=256,
        description="DECLARED, never verified. The service authenticates the caller with "
        "a shared token, and a token is not a person: the roles live in the console's "
        "session. || DECLARADO, nunca verificado.",
    )


class ActivateRunResponse(BaseModel):
    """The selection after activating. || La selección después de activar."""

    active: ActiveRunInfo


def _item(
    run: MirrorRun,
    *,
    active_run_id: str | None,
    active_env: str | None,
    build: TableBuild | None = None,
) -> ExtractionRunItem:
    return ExtractionRunItem(
        run_id=run.run_id,
        env=run.env,
        extractor_version=run.extractor_version,
        created_at_utc=run.created_at_utc,
        status=run.status,
        loaded_metadata=run.loaded_metadata,
        loaded_dependencies=run.loaded_dependencies,
        loaded_data=run.loaded_data,
        manifest_sha256=run.manifest_sha256,
        is_active=run.run_id == active_run_id and run.env == active_env,
        can_activate=run.loaded_data,
        # Presence of the row, not a non-zero count: a build that produced
        # nothing still ran, and conflating them hides a deployment gap.
        # || La presencia de la fila, no un conteo distinto de cero.
        tables_built=build is not None,
        tables_built_at=build.built_at if build else None,
        table_edge_count=build.edge_count if build else 0,
    )


def _active_info(active: ActiveRun) -> ActiveRunInfo:
    return ActiveRunInfo(
        run_id=active.run_id,
        env=active.env,
        origin=active.origin,
        reason=active.reason,
        activated_at=active.activated_at,
        activated_by=active.activated_by,
    )


@router.get("/runs", response_model=ExtractionRunList)
async def list_runs(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> ExtractionRunList:
    """Every run in the mirror for this tenant, newest first.

    Newest-first is for a person reading the list. It is NOT the service
    picking the newest — nothing here selects anything.

    || Todas las corridas del mirror para este tenant, la más nueva primero. Es
    para quien lee la lista y no una elección: acá nada selecciona nada.
    """
    settings = get_settings()
    tenant_id = settings.TENANT_ID

    active = await resolve_active_run(session, settings, tenant_id)
    runs = await list_mirror_runs(session, tenant_id)
    stamp_row = await get_stamp(session, tenant_id, settings.DOC_VERSION)
    builds = await list_table_builds(session, tenant_id)

    stamp = None
    if stamp_row is not None:
        stamp = CorpusStampInfo(
            run_id=stamp_row.run_id,
            env=stamp_row.env,
            doc_version=stamp_row.doc_version,
            stamped_at=stamp_row.stamped_at,
            rows_updated=stamp_row.rows_updated,
            matches_active=(
                stamp_row.run_id == active.run_id and stamp_row.env == active.env
            ),
        )

    return ExtractionRunList(
        active=_active_info(active),
        stamp=stamp,
        runs=[
            _item(
                run,
                active_run_id=active.run_id,
                active_env=active.env,
                build=builds.get((run.env, run.run_id)),
            )
            for run in runs
        ],
    )


@router.post("/runs/{run_id}/activate", response_model=ActivateRunResponse)
async def activate(
    run_id: str,
    body: ActivateRunRequest | None = None,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ActivateRunResponse:
    """Make ``run_id`` the run the service reads from.

    Two refusals, each with its own code and neither silent:

    * **404** — the mirror has no such run for this tenant. Accepting it would
      store a selection pointing at nothing.
    * **409** — the run exists but its data is not loaded. The navigation tree
      comes from `business_data`, so activating it would leave every code
      unresolved with the service up and answering worse.

    A value in `BUSINESS_DB_RUN_ID` is NOT a refusal. It is the default, not a
    lock: whoever operates the product outranks whoever deploys it for this
    decision.

    || Hace que ``run_id`` sea la corrida de la que lee el servicio. Dos
    rechazos, cada uno con su código y ninguno en silencio. Un valor en
    `BUSINESS_DB_RUN_ID` NO es motivo de rechazo: es el default, no un candado.
    """
    settings = get_settings()
    tenant_id = settings.TENANT_ID

    run = await find_mirror_run(session, tenant_id, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"El mirror no tiene la corrida {run_id!r} para este cliente. "
                f"|| The mirror has no run {run_id!r} for this tenant."
            ),
        )

    try:
        await activate_run(
            session, tenant_id=tenant_id, run=run, activated_by=_declared_by(body)
        )
    except RunNotLoaded as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    await session.commit()
    active = await resolve_active_run(session, settings, tenant_id)
    return ActivateRunResponse(active=_active_info(active))


def _declared_by(body: ActivateRunRequest | None) -> str | None:
    """The caller's claim about who is acting, or nothing.

    Never invents an author. `"unknown"` in the column would be indistinguishable
    from somebody actually named that, and worse, would read as a record.

    || Lo que declara quien llama, o nada. Nunca se inventa un autor: un
    `"unknown"` en la columna sería indistinguible de alguien que se llame así,
    y peor, se leería como un registro.
    """
    if body is None or body.activated_by is None:
        return None
    declared = body.activated_by.strip()
    return declared or None
