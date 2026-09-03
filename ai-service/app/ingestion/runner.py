"""Corre el pipeline como un trabajo en background y le escribe el estado.

Este módulo es el puente entre ``pipeline.py`` —que no sabe nada de HTTP ni de
jobs— y la tabla ``ingestion_jobs``. El pipeline reporta por ``progress``, y acá
ese callback escribe una fila.

Los pasos corren en un thread: son bloqueantes por dentro (``COPY`` de psycopg,
lectura de disco, llamadas sincrónicas al embedder) y ejecutarlos en el event
loop dejaría a la API sin responder durante minutos.

|| Runs the pipeline as a background job and writes its state.

This module is the bridge between ``pipeline.py`` -- which knows nothing about
HTTP or jobs -- and the ``ingestion_jobs`` table. The pipeline reports through
``progress``, and here that callback writes a row.

The steps run in a thread: they are blocking inside (psycopg's ``COPY``, disk
reads, synchronous embedder calls) and running them on the event loop would
leave the API unresponsive for minutes.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.foundation.persistence.database import get_async_session_factory
from app.ingestion import pipeline
from app.ingestion.jobs import FAILED, RUNNING, SUCCEEDED, IngestionJobRow, now

logger = structlog.get_logger(__name__)

CHUNK = "chunk"
EMBED = "embed"
LOAD = "load"
RESET = "reset"

# The order the steps have to run in. Not the order the caller sent them:
# embedding a corpus that has not been chunked yet is not a preference, it is a
# mistake, and sorting here means the endpoint does not have to validate it.
# || El orden en que los pasos TIENEN que correr. No el orden en que los mandó
# quien llama: embeber un corpus que todavía no se troceó no es una preferencia,
# es un error, y ordenarlos acá evita que el endpoint lo tenga que validar.
STEP_ORDER = (RESET, CHUNK, EMBED, LOAD)

DEFAULT_STEPS = (CHUNK, EMBED, LOAD)


def ordered(steps: list[str]) -> list[str]:
    """The requested steps, in the only order that works.

    || Los pasos pedidos, en el único orden que funciona.
    """
    return [step for step in STEP_ORDER if step in set(steps)]


class AlreadyRunning(RuntimeError):
    """Otro trabajo ya está corriendo. || Another job is already running."""


async def create_job(session, *, steps: list[str]) -> IngestionJobRow:
    """Insert the job as ``running``, which is also how the guard sees it.

    Raises ``AlreadyRunning`` when the database refuses the insert. That refusal
    is the REAL guard: the check the endpoint does first is only there to give a
    good error message, and checking-then-inserting is a race that two processes
    lose. It was lost -- two rebuilds got through and deadlocked.

    || Inserta el trabajo como ``running``, que es también como lo ve la guarda.
    Levanta ``AlreadyRunning`` cuando la base rechaza el insert. Ese rechazo es
    la guarda DE VERDAD: el chequeo que hace el endpoint antes existe solo para
    dar un buen mensaje, y chequear-y-después-insertar es una carrera que dos
    procesos pierden. Se perdió — dos rebuilds pasaron y se trabaron.
    """
    settings = get_settings()
    row = IngestionJobRow(
        id=str(uuid.uuid4()),
        tenant_id=settings.TENANT_ID,
        doc_version=settings.DOC_VERSION,
        status=RUNNING,
        steps=steps,
        result={},
        progress={},
        started_at=now(),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise AlreadyRunning(
            "Another ingestion job is already running. || Ya hay otro trabajo de "
            "ingesta corriendo."
        ) from error
    return row


async def running_job(session) -> IngestionJobRow | None:
    """The job already running, if any.

    Two rebuilds would write the same ``data/chunks/`` and the same table, so
    the second one is refused rather than interleaved.

    || El trabajo que ya está corriendo, si hay. Dos rebuilds escribirían el
    mismo ``data/chunks/`` y la misma tabla, así que el segundo se rechaza en
    lugar de entrelazarse.
    """
    result = await session.execute(
        select(IngestionJobRow).where(IngestionJobRow.status == RUNNING).limit(1)
    )
    return result.scalar_one_or_none()


def _run_steps(job_id: str, steps: list[str], options: dict, report) -> dict:
    """The blocking part. Runs in a thread; talks to the DB through ``report``.

    || La parte bloqueante. Corre en un thread; habla con la base por ``report``.
    """
    settings = get_settings()
    chunks_dir = Path(options.get("chunks_dir") or "data/chunks")
    results: dict[str, dict] = {}

    for step in steps:
        report(current_step=step)
        if step == RESET:
            outcome = pipeline.reset_corpus(
                tenant_id=settings.TENANT_ID,
                doc_version=settings.DOC_VERSION,
                progress=lambda **fields: report(progress=fields),
            )
        elif step == CHUNK:
            from app.dependencies import get_corpus_source

            outcome = pipeline.chunk_corpus(
                source=get_corpus_source(),
                out_dir=chunks_dir,
                modules=options.get("modules"),
                progress=lambda **fields: report(progress=fields),
            )
        elif step == EMBED:
            outcome = pipeline.embed_corpus(
                chunks_dir=chunks_dir,
                modules=options.get("modules"),
                dry_run=options.get("dry_run", False),
                progress=lambda **fields: report(progress=fields),
            )
        elif step == LOAD:
            outcome = pipeline.load_corpus(
                chunks_dir=chunks_dir,
                modules=options.get("modules"),
                prune=options.get("prune", False),
                dry_run=options.get("dry_run", False),
                progress=lambda **fields: report(progress=fields),
            )
        else:  # pragma: no cover - `ordered()` cannot produce anything else.
            raise ValueError(f"Unknown step: {step}")

        # `summary()` where a step has one: an EmbedStepResult carries the
        # runner's objects and the manifest, and neither is JSON.
        # || `summary()` donde el paso lo tenga: un EmbedStepResult lleva los
        # objetos del runner y el manifiesto, y ninguno es JSON.
        results[step] = (
            outcome.summary() if hasattr(outcome, "summary") else asdict(outcome)
        )
        report(result=dict(results))
    return results


async def run_job(job_id: str, steps: list[str], options: dict) -> None:
    """Run the job to completion and record how it ended.

    Every exception is caught: a background task that dies with an unhandled
    error leaves the row stuck on ``running`` forever, and the guard would then
    refuse every later rebuild.

    || Corre el trabajo hasta el final y registra cómo terminó. Toda excepción se
    captura: una tarea de background que muere con un error sin manejar deja la
    fila clavada en ``running`` para siempre, y la guarda rechazaría todos los
    rebuilds siguientes.
    """
    factory = get_async_session_factory()
    loop = asyncio.get_running_loop()
    started = time.perf_counter()

    def report(**fields) -> None:
        # Scheduled onto the loop from the worker thread, so the write happens
        # on the loop's session and not on the thread's.
        # || Se agenda en el loop desde el thread, así la escritura pasa en la
        # sesión del loop y no en la del thread.
        asyncio.run_coroutine_threadsafe(_write(factory, job_id, fields), loop)

    try:
        results = await asyncio.to_thread(_run_steps, job_id, steps, options, report)
        await _write(
            factory,
            job_id,
            {
                "status": SUCCEEDED,
                "result": results,
                "current_step": None,
                "finished_at": now(),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        logger.info("ingestion_job_succeeded", job_id=job_id, steps=steps)
    except Exception as error:  # noqa: BLE001 - see the docstring.
        await _write(
            factory,
            job_id,
            {
                "status": FAILED,
                # The message and not the traceback: this is read over HTTP.
                # || El mensaje y no el traceback: esto se lee por HTTP.
                "error": f"{type(error).__name__}: {error}",
                "finished_at": now(),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        logger.error("ingestion_job_failed", job_id=job_id, error=str(error))


async def _write(factory, job_id: str, fields: dict) -> None:
    async with factory() as session:
        await session.execute(
            update(IngestionJobRow).where(IngestionJobRow.id == job_id).values(**fields)
        )
        await session.commit()
