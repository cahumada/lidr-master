"""Which mirror run the service works with, and what stamped the corpus.

The mirror (`visualtime.*`) accumulates extractor runs — three at the time of
writing, across two environments and with different degrees of load — and the
service reads from exactly ONE. This module owns that relationship: which run
is active, who said so, and which run the corpus metadata was stamped from.

Two rules shape everything here.

**The selection lives in our schema, never in the mirror.**
`visualtime.extraction_runs` has an obvious place for an `is_active` column and
putting one there would be a mistake: that table is defined and written by
`dw-oracle-extractor`, which has its own release cycle and its own DDL. Adding
a column from here turns the mirror into shared space with two owners, which is
the very reason it lives in a separate schema with read-only access. The
selection is OUR relationship with the mirror, not an attribute of it.

**`BUSINESS_DB_RUN_ID` is a seed, not an override.** `providers_store` holds
both mechanisms and this one takes the seed: which mirror run to work with is a
product-operation decision, not secret management, so whoever operates the
product outranks whoever deploys it — while a fresh install still has to boot
working before anyone opens the console. The seed is NEVER materialized as a
row: a row would make it look like somebody chose that run, and nobody did. It
resolves at read time and the active run reports its origin.

|| Con qué corrida del mirror trabaja el servicio, y con cuál se estampó el
corpus. La selección vive en NUESTRO esquema y nunca en el mirror: esa tabla la
escribe otro repo con su propio DDL, y agregarle una columna desde acá la
volvería un espacio compartido con dos dueños. `BUSINESS_DB_RUN_ID` es SEMILLA
y no override: con qué corrida se trabaja es una decisión de operación del
producto, así que quien opera está por encima de quien despliega, y aun así una
instalación nueva arranca funcionando. La semilla NUNCA se materializa como
fila: una fila haría parecer que alguien eligió, y nadie eligió.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Settings
from app.foundation.persistence.database import Base

log = structlog.get_logger()

# Where the active run comes from. `selected` means a row says so; `default`
# means nobody chose and the configuration supplied one; `none` means neither.
# || De dónde sale la corrida vigente. `none` es que no hay ninguna de las dos.
RunOrigin = Literal["selected", "default", "none"]

# The load flag the navigation tree actually needs. The three flags are
# independent, and this is the one whose absence breaks resolution: the WINDOWS
# tree is built from `business_data`.
# || La bandera de carga que el árbol necesita de verdad. Las tres son
# independientes y ésta es la que rompe la resolución si falta.
REQUIRED_LOAD_FLAG = "loaded_data"

_ACTIVE = "active"
_RETIRED = "retired"


class BusinessDbSelectionRow(Base):
    """One mirror run this client has selected, active or retired.

    Rows accumulate rather than being overwritten: which runs were active
    before, and who activated each, is the only history of a decision that
    changes what every answer says.

    || Una corrida del mirror que este cliente eligió, activa o retirada. Las
    filas se acumulan en vez de sobreescribirse: qué corridas estuvieron
    activas antes, y quién activó cada una, es el único historial de una
    decisión que cambia lo que dice cada respuesta.
    """

    __tablename__ = "business_db_selection"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # The mirror keys a run by (tenant, env, run_id), so the selection has to
    # carry `env` too — the same `run_id` string in DEV and PROD is two runs.
    # || El mirror identifica una corrida por (tenant, env, run_id), así que la
    # selección también lleva `env`: el mismo `run_id` en DEV y en PROD son dos
    # corridas distintas.
    env: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # 'active' | 'retired'. Text and not an enum type, like `corpus_versions`:
    # adding a state stays a data change instead of a migration on a Postgres
    # type.
    # || Texto y no un tipo enum, igual que `corpus_versions`: agregar un estado
    # sigue siendo un cambio de datos y no una migración sobre un tipo.
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=_ACTIVE)

    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # DECLARED by the caller, never verified. The service authenticates the
    # CALLER with a shared token (`add-service-authentication`) and that is not
    # a person: the roles live in the console's session token and the admin gate
    # is applied there. So this column records what the console said, and it is
    # documented as declared everywhere it surfaces. An audit trail that looks
    # authoritative without being one is worse than not having it.
    # || DECLARADO por quien llama, nunca verificado. El servicio autentica al
    # LLAMADOR con un token compartido, y eso no es una persona: los roles viven
    # en el token de sesión de la consola y el gate de administrador se aplica
    # ahí. Un registro que parece autoritativo sin serlo es peor que no tenerlo.
    activated_by: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "env", "run_id", name="uq_business_db_selection_tenant_env_run"
        ),
        # At most one active run per client, enforced by the DATABASE. The same
        # rule held only in application code breaks under two concurrent
        # processes — the reasoning `corpus_versions` already wrote down for its
        # single active version.
        # NOT keyed by `env`: the service reads from one run, period. Allowing
        # one active per environment would mean two answers depending on which
        # env a caller happened to ask about.
        # || A lo sumo una corrida activa por cliente, garantizado por la BASE.
        # NO va por `env`: el servicio lee de una corrida y punto. Una activa
        # por ambiente significaría dos respuestas según el env que se pidiera.
        Index(
            "uq_business_db_selection_one_active_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class BusinessDbStampRow(Base):
    """Which run stamped the corpus metadata, so the drift is visible.

    `window_status` is stamped onto chunks from one concrete run. Activating a
    different run later leaves that column stale, and invisible drift between
    what is stamped and what is active is the kind of defect nobody finds until
    an answer has already gone out wrong. One row per
    ``(tenant_id, doc_version)``: a stamp replaces the previous one for that
    corpus version, because there is only ever one stamped state.

    || Con qué corrida se estampó la metadata del corpus, para que el desfasaje
    se vea. Una fila por ``(tenant_id, doc_version)``: un estampado reemplaza al
    anterior de esa versión, porque solo hay un estado estampado a la vez.
    """

    __tablename__ = "business_db_stamp"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[str] = mapped_column(String(128), nullable=False)
    env: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)

    stamped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # How many chunk rows the stamp actually touched. Zero is a real and
    # interesting answer — it means the corpus had nothing to stamp — so it is
    # recorded rather than treated as a failure.
    # || Cuántas filas tocó el estampado. Cero es una respuesta real e
    # interesante —el corpus no tenía nada que estampar— así que se registra.
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "doc_version", name="uq_business_db_stamp_tenant_doc_version"
        ),
    )


@dataclass(frozen=True)
class ActiveRun:
    """The run in force, where it came from, and why there is none.

    ``run_id`` is ``None`` only when ``origin`` is ``"none"``, and then
    ``reason`` says why in words a person can act on. Returning a reason rather
    than a bare ``None`` is the point: "no active run" and "no active run
    because nothing is configured either" send an operator to different places.

    || La corrida en vigor, de dónde salió, y por qué no hay ninguna. Devolver
    una razón y no un ``None`` pelado es el punto: «no hay corrida» y «no hay
    corrida porque tampoco hay configuración» mandan a lugares distintos.
    """

    run_id: str | None
    env: str
    origin: RunOrigin
    reason: str | None = None
    activated_at: datetime | None = None
    activated_by: str | None = None

    @property
    def resolved(self) -> bool:
        """Whether there is a run to read from. || Si hay corrida de la cual leer."""
        return self.run_id is not None


def _decide(
    selected: tuple[str, str, datetime | None, str | None] | None, settings: Settings
) -> ActiveRun:
    """The precedence rule, in one place.

    Two callers fetch the selected row two ways — one on the request's async
    session, one on a psycopg connection for the batch path — and both come
    here to decide. The rule existing twice is how the async path and the batch
    path start disagreeing about which run is live, which is the exact defect
    this change is about.

    Never "the most recent run": a run that appeared in the mirror is not a run
    somebody decided to serve, and picking the latest would make what the
    service answers change without anyone having chosen it.

    || La regla de precedencia, en un solo lugar. Dos llamadores traen la fila
    de dos maneras y los dos vienen acá a decidir: que la regla exista dos veces
    es cómo el camino async y el batch empiezan a no coincidir sobre qué corrida
    está viva, que es exactamente el defecto del que trata este change.
    """
    if selected is not None:
        run_id, env, activated_at, activated_by = selected
        return ActiveRun(
            run_id=run_id,
            env=env,
            origin="selected",
            activated_at=activated_at,
            activated_by=activated_by,
        )

    configured = (settings.BUSINESS_DB_RUN_ID or "").strip()
    if configured:
        return ActiveRun(run_id=configured, env=settings.BUSINESS_DB_ENV, origin="default")

    return ActiveRun(
        run_id=None,
        env=settings.BUSINESS_DB_ENV,
        origin="none",
        reason=(
            "No hay corrida activa seleccionada y `BUSINESS_DB_RUN_ID` está vacío. "
            "Activá una corrida o configurá el valor por defecto; el servicio NO "
            "elige la más reciente por su cuenta. || No active run selected and "
            "`BUSINESS_DB_RUN_ID` is empty. The service does not pick the latest."
        ),
    )


async def resolve_active_run(
    session: AsyncSession, settings: Settings, tenant_id: str | None = None
) -> ActiveRun:
    """The active run: the selected row wins, then the configured default.

    Resolving from the configuration writes NOTHING. See the module docstring:
    a seeded row would be indistinguishable from a choice.

    || La corrida activa: gana la fila seleccionada, después el default de
    configuración. Resolver por default NO escribe ninguna fila.
    """
    tenant = tenant_id or settings.TENANT_ID
    result = await session.execute(
        select(BusinessDbSelectionRow).where(
            BusinessDbSelectionRow.tenant_id == tenant,
            BusinessDbSelectionRow.status == _ACTIVE,
        )
    )
    row = result.scalar_one_or_none()
    selected = (
        (row.run_id, row.env, row.activated_at, row.activated_by) if row is not None else None
    )
    return _decide(selected, settings)


_SELECTED_SQL = """
    SELECT run_id, env, activated_at, activated_by
    FROM business_db_selection
    WHERE tenant_id = %s AND status = 'active'
    LIMIT 1
"""


def resolve_active_run_sync(
    database_url: str, settings: Settings, tenant_id: str | None = None
) -> ActiveRun:
    """The same decision, for the paths that cannot await.

    The rebuild runs in a thread (`ingestion/runner.py` `_run_steps`) and the
    scripts are plain `main()`s, so neither can hold the request's async
    session. They still have to resolve the SELECTED run and not the configured
    one: a batch that chunks against a run nobody chose stamps the corpus with
    it, which is how the drift this change exists to expose would get created
    by the very tooling meant to fix it.

    An unreachable database is not fatal here — it falls through to the
    configured default, which is the behaviour that existed before selection.

    || La misma decisión, para los caminos que no pueden await. El rebuild corre
    en un thread y los scripts son un `main()`, así que ninguno tiene la sesión
    async del request. Igual tienen que resolver la corrida SELECCIONADA y no la
    configurada: un batch que trocea contra una corrida que nadie eligió estampa
    el corpus con ella, que es cómo el desfasaje que este change existe para
    mostrar terminaría creado por la herramienta que lo iba a arreglar. Una base
    inalcanzable no es fatal acá: cae al default, que es lo que existía antes.
    """
    import psycopg

    tenant = tenant_id or settings.TENANT_ID
    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(url) as connection, connection.cursor() as cursor:
            cursor.execute(_SELECTED_SQL, (tenant,))
            row = cursor.fetchone()
    except Exception as error:  # noqa: BLE001 — any failure means "no selection readable".
        log.warning("business_db_selection_unreadable", error=str(error))
        row = None

    selected = (row[0], row[1], row[2], row[3]) if row else None
    return _decide(selected, settings)


@dataclass(frozen=True)
class MirrorRun:
    """One row of `visualtime.extraction_runs`, as the chooser needs it.

    || Una fila de `visualtime.extraction_runs`, como la necesita quien elige.
    """

    tenant: str
    env: str
    run_id: str
    extractor_version: str | None
    created_at_utc: datetime | None
    status: str | None
    loaded_metadata: bool
    loaded_dependencies: bool
    loaded_data: bool
    manifest_sha256: str | None


# Read-only, and the schema is named explicitly rather than left to
# `search_path`: this is another repo's table and the query says so at a glance.
# || Solo lectura, y el esquema se nombra explícito en vez de dejarlo al
# `search_path`: es una tabla de otro repo y la consulta lo dice de un vistazo.
_RUNS_SQL = """
    SELECT tenant, env, run_id, extractor_version, created_at_utc, status,
           loaded_metadata, loaded_dependencies, loaded_data, manifest_sha256
    FROM visualtime.extraction_runs
    WHERE tenant = :tenant
    ORDER BY created_at_utc DESC NULLS LAST, run_id DESC
"""


async def list_mirror_runs(session: AsyncSession, tenant_id: str) -> list[MirrorRun]:
    """Every run the mirror holds for this client, newest first.

    Ordered newest-first for a human reading a list, which is NOT the same as
    the service picking the newest — nothing here selects anything.

    || Todas las corridas que el mirror tiene para este cliente, la más nueva
    primero. Ordenar así es para quien lee la lista, y no es lo mismo que el
    servicio elija la más nueva: acá nada selecciona nada.
    """
    result = await session.execute(text(_RUNS_SQL), {"tenant": tenant_id})
    return [
        MirrorRun(
            tenant=row.tenant,
            env=row.env,
            run_id=row.run_id,
            extractor_version=row.extractor_version,
            created_at_utc=row.created_at_utc,
            status=row.status,
            loaded_metadata=bool(row.loaded_metadata),
            loaded_dependencies=bool(row.loaded_dependencies),
            loaded_data=bool(row.loaded_data),
            manifest_sha256=row.manifest_sha256,
        )
        for row in result
    ]


async def find_mirror_run(
    session: AsyncSession, tenant_id: str, run_id: str, env: str | None = None
) -> MirrorRun | None:
    """One run by id, optionally narrowed to an environment.

    Without ``env`` a `run_id` that exists in two environments is ambiguous, so
    the caller gets the first by the same ordering as the listing and the
    endpoint asks for `env` when it matters.

    || Una corrida por id, opcionalmente acotada a un ambiente.
    """
    for run in await list_mirror_runs(session, tenant_id):
        if run.run_id != run_id:
            continue
        if env is not None and run.env != env:
            continue
        return run
    return None


class RunNotLoaded(ValueError):
    """The run exists but cannot serve the navigation tree.

    || La corrida existe pero no puede servir el árbol de navegación.
    """


async def activate_run(
    session: AsyncSession,
    *,
    tenant_id: str,
    run: MirrorRun,
    activated_by: str | None = None,
) -> BusinessDbSelectionRow:
    """Make ``run`` the active one, retiring whatever was active before.

    Refuses a run whose data is not loaded. The WINDOWS tree comes from
    `business_data`, so activating a run without it would leave every code
    unresolved — empty breadcrumbs, no window type, no status — with the
    service up and answering worse without saying why.

    Retire-then-insert in one transaction, and the partial unique index is what
    actually guarantees the invariant: if two callers race, one of them fails on
    the index instead of both believing they won.

    || Hace activa a ``run`` y retira la anterior. Rechaza una corrida sin datos
    cargados: el árbol sale de `business_data`, y activarla dejaría todos los
    códigos sin resolver con el servicio arriba y respondiendo peor sin decir
    por qué. Retirar e insertar en una transacción, y el que garantiza el
    invariante es el índice parcial: si dos llamadas compiten, una falla en el
    índice en vez de que las dos crean haber ganado.
    """
    if not run.loaded_data:
        raise RunNotLoaded(
            f"La corrida {run.run_id!r} tiene {REQUIRED_LOAD_FLAG}=false: el árbol de "
            "navegación sale de `business_data` y activarla dejaría todos los códigos "
            f"sin resolver. || Run {run.run_id!r} has {REQUIRED_LOAD_FLAG}=false."
        )

    await session.execute(
        update(BusinessDbSelectionRow)
        .where(
            BusinessDbSelectionRow.tenant_id == tenant_id,
            BusinessDbSelectionRow.status == _ACTIVE,
        )
        .values(status=_RETIRED)
    )

    # A run selected, retired and selected again is the same (tenant, env, run)
    # row, so reuse it rather than violating the unique constraint.
    # || Una corrida elegida, retirada y vuelta a elegir es la misma fila.
    existing = await session.execute(
        select(BusinessDbSelectionRow).where(
            BusinessDbSelectionRow.tenant_id == tenant_id,
            BusinessDbSelectionRow.env == run.env,
            BusinessDbSelectionRow.run_id == run.run_id,
        )
    )
    row = existing.scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        row = BusinessDbSelectionRow(
            tenant_id=tenant_id,
            env=run.env,
            run_id=run.run_id,
            status=_ACTIVE,
            activated_at=now,
            activated_by=activated_by,
        )
        session.add(row)
    else:
        row.status = _ACTIVE
        row.activated_at = now
        row.activated_by = activated_by

    await session.flush()
    log.info(
        "business_db_run_activated",
        tenant_id=tenant_id,
        env=run.env,
        run_id=run.run_id,
        activated_by_declared=activated_by,
    )
    return row


async def get_stamp(
    session: AsyncSession, tenant_id: str, doc_version: str
) -> BusinessDbStampRow | None:
    """Which run stamped this corpus version, if any did.

    || Con qué corrida se estampó esta versión del corpus, si alguna lo hizo.
    """
    result = await session.execute(
        select(BusinessDbStampRow).where(
            BusinessDbStampRow.tenant_id == tenant_id,
            BusinessDbStampRow.doc_version == doc_version,
        )
    )
    return result.scalar_one_or_none()


async def record_stamp(
    session: AsyncSession,
    *,
    tenant_id: str,
    doc_version: str,
    env: str,
    run_id: str,
    rows_updated: int,
) -> BusinessDbStampRow:
    """Record that the corpus was stamped from ``run_id``, replacing any prior.

    || Registra que el corpus se estampó desde ``run_id``, reemplazando el
    anterior de esa versión.
    """
    row = await get_stamp(session, tenant_id, doc_version)
    now = datetime.now(UTC)
    if row is None:
        row = BusinessDbStampRow(
            tenant_id=tenant_id,
            doc_version=doc_version,
            env=env,
            run_id=run_id,
            stamped_at=now,
            rows_updated=rows_updated,
        )
        session.add(row)
    else:
        row.env = env
        row.run_id = run_id
        row.stamped_at = now
        row.rows_updated = rows_updated

    await session.flush()
    log.info(
        "business_db_stamp_recorded",
        tenant_id=tenant_id,
        doc_version=doc_version,
        env=env,
        run_id=run_id,
        rows_updated=rows_updated,
    )
    return row
