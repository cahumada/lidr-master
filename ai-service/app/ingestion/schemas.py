"""Contratos de la ingesta batch. || Batch ingestion contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.ingestion.runner import CHUNK, EMBED, LOAD


class RebuildRequest(BaseModel):
    """Body de ``POST /corpus/rebuild``. || Body of ``POST /corpus/rebuild``."""

    steps: list[str] | None = Field(
        default=None,
        description=f"Which steps to run: '{CHUNK}', '{EMBED}', '{LOAD}'. They are reordered "
        "to the only sequence that works, so the order sent does not matter. Default: all "
        f"three. || Qué pasos correr: '{CHUNK}', '{EMBED}', '{LOAD}'. Se reordenan a la única "
        "secuencia que funciona, así que el orden enviado no importa. Default: los tres.",
    )
    modules: list[str] | None = Field(
        default=None,
        description="Limit to these modules. Incompatible with `prune`, which needs the whole "
        "corpus to know what is missing. || Limitar a estos módulos. Incompatible con `prune`, "
        "que necesita el corpus entero para saber qué falta.",
    )
    prune: bool = Field(
        default=False,
        description="Delete the rows whose text is no longer anywhere in the corpus. This is "
        "the NON-destructive cleanup: it removes only what the corpus no longer has. "
        "|| Borrar las filas cuyo texto ya no está en ninguna parte del corpus. Es la limpieza "
        "NO destructiva: saca solo lo que el corpus ya no tiene.",
    )
    reset: bool = Field(
        default=False,
        description="DESTRUCTIVE: delete every row of this corpus before rebuilding. Requires "
        "`confirm_tenant_id` and `confirm_doc_version` to match the configured corpus. "
        "|| DESTRUCTIVO: borra todas las filas de este corpus antes de rehacerlo. Exige que "
        "`confirm_tenant_id` y `confirm_doc_version` coincidan con el corpus configurado.",
    )
    confirm_tenant_id: str | None = Field(
        default=None, description="Required with `reset`. || Requerido con `reset`."
    )
    confirm_doc_version: str | None = Field(
        default=None, description="Required with `reset`. || Requerido con `reset`."
    )
    dry_run: bool = Field(
        default=False,
        description="Plan and report without calling the embedding API or writing to the "
        "database. || Planificar y reportar sin llamar a la API de embeddings ni escribir en "
        "la base.",
    )


class RebuildStarted(BaseModel):
    """Respuesta de ``POST /corpus/rebuild``. || Response of ``POST /corpus/rebuild``."""

    job_id: str = Field(description="Poll `GET /corpus/jobs/{id}`. || Consultar en `GET /corpus/jobs/{id}`.")
    steps: list[str] = Field(description="The steps, in run order. || Los pasos, en orden de corrida.")
    status: str


class IngestionJob(BaseModel):
    """Un trabajo de ingesta. || One ingestion job."""

    id: str
    tenant_id: str
    doc_version: str
    status: str = Field(description="queued / running / succeeded / failed.")
    steps: list[str]
    current_step: str | None = None
    result: dict = Field(
        default_factory=dict,
        description="What each step produced, keyed by step name. "
        "|| Lo que produjo cada paso, por nombre de paso.",
    )
    progress: dict = Field(
        default_factory=dict,
        description="The last progress line, so a long step is not a black box while it runs. "
        "|| La última línea de progreso, para que un paso largo no sea una caja negra.",
    )
    error: str | None = Field(
        default=None,
        description="The message, never a stack trace. || El mensaje, nunca un stack trace.",
    )
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
