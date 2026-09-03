"""POST /corpus/rebuild y el estado de sus trabajos.

Existe para que apuntar el servicio a otra base —cambiar `DATABASE_URL`— no
obligue a tener una terminal y este repo clonado para poblarla.

**El pipeline lee un directorio local**, así que la API tiene que correr donde
está el corpus. La raíz sale de `Settings.CORPUS_ROOT` y NO de un parámetro:
aceptar una ruta arbitraria por HTTP es una lectura de disco arbitraria.

|| POST /corpus/rebuild and its jobs' state.

It exists so that pointing the service at another database -- changing
`DATABASE_URL` -- does not require a terminal and a clone of this repo to
populate it.

**The pipeline reads a local directory**, so the API has to run where the corpus
is. The root comes from `Settings.CORPUS_ROOT` and NOT from a parameter:
accepting an arbitrary path over HTTP is an arbitrary disk read.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.foundation.persistence.database import get_async_session
from app.ingestion.jobs import IngestionJobRow
from app.ingestion.runner import (
    CHUNK,
    DEFAULT_STEPS,
    RESET,
    AlreadyRunning,
    create_job,
    ordered,
    run_job,
    running_job,
)
from app.ingestion.schemas import IngestionJob, RebuildRequest, RebuildStarted

log = structlog.get_logger()

router = APIRouter(prefix="/corpus", tags=["corpus"])


def _as_job(row: IngestionJobRow) -> IngestionJob:
    return IngestionJob(
        id=row.id,
        tenant_id=row.tenant_id,
        doc_version=row.doc_version,
        status=row.status,
        steps=row.steps,
        current_step=row.current_step,
        result=row.result,
        progress=row.progress,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
    )


@router.post(
    "/rebuild",
    response_model=RebuildStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rebuild(
    payload: RebuildRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's DI idiom.
) -> RebuildStarted:
    """Start the pipeline and return the job's id. Does NOT wait for it.

    Measured: 12.5 s to chunk and 141 s to load against localhost, and embedding
    can be hours if the corpus text changed. None of that fits in a request.

    || Arranca el pipeline y devuelve el id del trabajo. NO espera. Medido:
    trocear 12,5 s y cargar 141 s contra localhost, y embeber puede ser horas si
    cambió el texto del corpus. Nada de eso cabe en un request.
    """
    settings = get_settings()

    if payload.reset:
        # A destructive step does not travel as a boolean. It has to spell out
        # which corpus it is wiping, and match: a stray `reset=true` in a shell
        # history should not empty a database.
        # || Un paso destructivo no viaja como booleano. Tiene que decir qué
        # corpus está borrando, y coincidir: un `reset=true` suelto en un
        # historial de shell no debería vaciar una base.
        confirmed = payload.confirm_tenant_id, payload.confirm_doc_version
        expected = settings.TENANT_ID, settings.DOC_VERSION
        if confirmed != expected:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "reset requires confirm_tenant_id and confirm_doc_version to match the "
                "configured corpus. || reset exige que confirm_tenant_id y "
                "confirm_doc_version coincidan con el corpus configurado.",
            )

    steps = ordered(list(payload.steps or DEFAULT_STEPS) + ([RESET] if payload.reset else []))

    # Only the chunking step reads the source markdown. Requiring the root for
    # every run would block the most useful case there is: pointing the service
    # at a new database and loading the corpus that is already on disk, which
    # needs no source documents at all.
    # || Solo el paso de chunking lee los markdown fuente. Exigir la raíz en toda
    # corrida bloquearía el caso más útil que hay: apuntar el servicio a una base
    # nueva y cargarle el corpus que ya está en disco, que no necesita ningún
    # documento fuente.
    if CHUNK in steps and settings.CORPUS_ROOT is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "CORPUS_ROOT is not configured, so there is nothing to chunk. Drop the 'chunk' "
            "step to load the corpus already on disk. || CORPUS_ROOT no está configurada, así "
            "que no hay nada que trocear. Saca el paso 'chunk' para cargar el corpus que ya "
            "está en disco.",
        )

    already = await running_job(session)
    if already is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Job {already.id} is already running. Two rebuilds would write the same "
            f"corpus directory and the same table. || El trabajo {already.id} ya está "
            f"corriendo. Dos rebuilds escribirían el mismo directorio y la misma tabla.",
        )

    try:
        row = await create_job(session, steps=steps)
    except AlreadyRunning as error:
        # The database refused it. The check above is the friendly message; this
        # is the guarantee.
        # || La base lo rechazó. El chequeo de arriba es el mensaje amable; esto
        # es la garantía.
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    options = {
        "root": str(settings.CORPUS_ROOT),
        "modules": payload.modules,
        "prune": payload.prune,
        "dry_run": payload.dry_run,
    }
    background.add_task(run_job, row.id, steps, options)

    log.info("rebuild_accepted", job_id=row.id, steps=steps, reset=payload.reset)
    return RebuildStarted(job_id=row.id, steps=steps, status=row.status)


@router.get("/jobs/{job_id}", response_model=IngestionJob)
async def job(
    job_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's DI idiom.
) -> IngestionJob:
    """One job's state, current step and what each step produced.

    || El estado de un trabajo, su paso actual y lo que produjo cada paso.
    """
    row = await session.get(IngestionJobRow, job_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No job {job_id}.")
    return _as_job(row)


@router.get("/jobs", response_model=list[IngestionJob])
async def jobs(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's DI idiom.
) -> list[IngestionJob]:
    """The latest jobs, newest first.

    || Los últimos trabajos, el más nuevo primero.
    """
    result = await session.execute(
        select(IngestionJobRow).order_by(IngestionJobRow.created_at.desc()).limit(limit)
    )
    return [_as_job(row) for row in result.scalars()]
