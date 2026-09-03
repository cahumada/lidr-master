"""Seguimiento de trabajos de ingesta, en Postgres y no en memoria.

El pipeline completo tarda minutos: trocear 12,5 s, cargar 141 s contra
localhost, y embeber puede ser horas si el corpus cambió. Eso no cabe en un
request HTTP, así que el trabajo corre en background y su estado vive en una
tabla.

En una tabla y no en un diccionario del proceso: un trabajo de minutos que se
pierde porque el proceso reinició no se puede diagnosticar después, y "no sé qué
pasó" es la peor respuesta posible frente a una carga a medio hacer.

|| Ingestion job tracking, in Postgres rather than in memory.

The whole pipeline takes minutes: 12.5 s to chunk, 141 s to load against
localhost, and embedding can be hours if the corpus changed. That does not fit
in an HTTP request, so the work runs in the background and its state lives in a
table.

In a table and not in a process dictionary: a job of several minutes that is
lost because the process restarted cannot be diagnosed afterwards, and "I don't
know what happened" is the worst possible answer to a half-finished load.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.foundation.persistence.database import Base

# The states a job can be in. `running` is what the concurrency guard looks for:
# two rebuilds would write the same `data/chunks/` and the same table.
# || Los estados posibles. `running` es lo que mira la guarda de concurrencia:
# dos rebuilds escribirían el mismo `data/chunks/` y la misma tabla.
QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"


class IngestionJobRow(Base):
    """One pipeline run, with what each step produced.

    || Una corrida del pipeline, con lo que produjo cada paso.
    """

    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=QUEUED)
    # Which steps were asked for, in order, and which one is running now.
    # || Qué pasos se pidieron, en orden, y cuál corre ahora.
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    current_step: Mapped[str | None] = mapped_column(String(32))

    # What each step produced, keyed by step name. JSONB and not columns: the
    # shape differs per step and adding a step should not be a migration.
    # || Lo que produjo cada paso, por nombre de paso. JSONB y no columnas: la
    # forma cambia por paso y agregar un paso no debería ser una migración.
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # The last progress line, so a long step is not a black box while it runs.
    # || La última línea de progreso, para que un paso largo no sea una caja
    # negra mientras corre.
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # The message, never a stack trace: this is read over HTTP and a trace would
    # leak paths and library layout to whoever can call the endpoint.
    # || El mensaje, nunca un stack trace: esto se lee por HTTP y un trace
    # filtraría rutas y la estructura de las librerías a quien pueda llamar.
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        # The listing is "the latest jobs".
        # || El listado es "los últimos trabajos".
        Index("ix_ingestion_jobs_created", "created_at"),
        # AT MOST ONE running job, enforced by the DATABASE. The application
        # also checks, but only to give a good error message: the same rule held
        # in application code alone breaks under two processes, and it did --
        # two rebuilds got through and deadlocked against each other while one
        # was DELETEing 57101 rows and the other was COPYing into them.
        #
        # Unique on `status` restricted to the running rows, which is how
        # Postgres expresses "at most one of these". The same technique
        # `corpus_versions` already uses for its single active version.
        # || A LO SUMO UN trabajo corriendo, garantizado por la BASE. La
        # aplicación también chequea, pero solo para dar un buen mensaje de
        # error: la misma regla sostenida solo en código de aplicación se rompe
        # con dos procesos, y se rompió — dos rebuilds pasaron y se trabaron
        # entre sí mientras uno borraba 57101 filas y el otro copiaba sobre
        # ellas.
        #
        # Único sobre `status` restringido a las filas que corren, que es como
        # Postgres dice "a lo sumo una de estas". La misma técnica que ya usa
        # `corpus_versions` para su única versión activa.
        Index(
            "uq_ingestion_jobs_one_running",
            "status",
            unique=True,
            postgresql_where=text(f"status = '{RUNNING}'"),
        ),
    )


def now() -> datetime:
    """Timezone-aware, because the column is. || Con zona, porque la columna la tiene."""
    return datetime.now(UTC)
