"""Providers and their models, in the database.

What lives here and why it is a table rather than an env var: model ids change
often, and adding one should not need a redeploy; provider credentials are
rotated by whoever operates the service, not by whoever ships it. The tables
are seeded from the code registry and `ANSWER_MODEL_CATALOG` on first boot, so
a fresh install behaves exactly as before and the console becomes the place to
change it afterwards.

The credential column holds **ciphertext only** — see
`app/foundation/secrets.py`. An environment variable still wins over a stored
key, so a deployment that prefers real secret management keeps working
untouched and the database copy is the fallback, not the authority.

`wire` is what makes a NEW provider a row instead of a code change: anything
that speaks OpenAI's `/chat/completions` (Groq, DeepSeek, Together, a local
vLLM) is `openai_compatible` plus a `base_url`. It is validated against the
wires the code actually implements — a row claiming a wire nobody wrote would
be a lie the console would happily display.

|| Proveedores y sus modelos, en la base. Es tabla y no env var porque los ids
de modelo cambian seguido y agregar uno no debería necesitar un redeploy, y
porque las credenciales las rota quien opera el servicio, no quien lo publica.
Las tablas se siembran del registro de código y de `ANSWER_MODEL_CATALOG` en el
primer arranque.

La columna de credencial guarda SOLO ciphertext. Una variable de entorno le
gana a una clave guardada: la copia en la base es el fallback, no la autoridad.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Settings
from app.foundation.persistence.database import Base

log = structlog.get_logger()


class ProviderRow(Base):
    """One generation provider. || Un proveedor de generación."""

    __tablename__ = "providers"

    # The id is the key the rest of the system uses ("openai", "anthropic",
    # "moonshot", or a new one somebody adds), not a surrogate integer: it
    # appears in `agent_profiles.provider` and in the API, and a stable
    # human-readable id is what keeps those readable.
    # || El id es la clave que usa el resto del sistema y no un entero
    # surrogate: aparece en `agent_profiles.provider` y en la API.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)

    # Which adapter talks to it. Constrained in code to the wires that exist.
    # || Qué adaptador le habla. Restringido en código a los wires que existen.
    wire: Mapped[str] = mapped_column(String(32), nullable=False)

    base_url: Mapped[str | None] = mapped_column(String(255))

    # The env var that overrides a stored key for this provider. Kept as data
    # so a provider added from the console can declare one too.
    # || La env var que le gana a la clave guardada. Es dato para que un
    # proveedor agregado desde la consola también pueda declarar una.
    api_key_setting: Mapped[str | None] = mapped_column(String(64))

    # CIPHERTEXT ONLY. Never returned by the API, never logged.
    # || SOLO CIPHERTEXT. Nunca lo devuelve la API, nunca se loguea.
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text)

    # Last few characters, so a human can tell WHICH key is loaded without the
    # key being readable.
    # || Últimos caracteres, para saber CUÁL clave está cargada sin que la
    # clave sea legible.
    api_key_hint: Mapped[str | None] = mapped_column(String(16))

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProviderModelRow(Base):
    """One selectable model of one provider. || Un modelo elegible de un proveedor."""

    __tablename__ = "provider_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(96), nullable=False)

    # Whether this model accepts a `temperature`. Seeded from what the code
    # knows and editable afterwards: a provider can ship a model whose
    # behaviour the code has never seen, and waiting for a deploy to be able
    # to say "this one rejects sampling" is how a broken 400 stays broken.
    # || Si este modelo acepta `temperature`. Se siembra con lo que el código
    # sabe y después se edita: un proveedor puede sacar un modelo que el código
    # nunca vio, y esperar un deploy para poder decir "este rechaza sampling"
    # es cómo un 400 se queda roto.
    supports_temperature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Curation: hidden models stay in the table (so a refresh does not keep
    # re-offering them) but are not offered in the console.
    # || Curaduría: los ocultos quedan en la tabla (para que un refresh no los
    # vuelva a ofrecer) pero no se ofrecen en la consola.
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "model", name="uq_provider_models_pair"),
        Index("ix_provider_models_provider", "provider_id"),
    )


@dataclass(frozen=True)
class ResolvedProvider:
    """A provider as the rest of the service sees it, credentials resolved.

    ``key_source`` is what the console shows: an operator needs to know
    whether the key in force came from the environment or from the database,
    because that is where they have to go to change it.

    || Un proveedor como lo ve el resto del servicio, con la credencial
    resuelta. ``key_source`` es lo que muestra la consola: quien opera necesita
    saber si la clave vigente vino del entorno o de la base, porque es ahí
    donde tiene que ir a cambiarla.
    """

    id: str
    label: str
    wire: str
    base_url: str | None
    enabled: bool
    note: str | None
    api_key_setting: str | None
    api_key: str | None
    api_key_hint: str | None
    key_source: str  # "env" | "stored" | "none"

    @property
    def available(self) -> bool:
        """Usable right now: enabled and holding a credential.

        || Usable ahora: habilitado y con credencial.
        """
        return self.enabled and bool(self.api_key)


def _env_key(row_setting: str | None, settings: Settings) -> str:
    if not row_setting:
        return ""
    return str(getattr(settings, row_setting, "") or "")


def resolve_provider(row: ProviderRow, settings: Settings) -> ResolvedProvider:
    """Merge a provider row with the environment, environment winning.

    The env var wins so a deployment using real secret management is never
    silently overridden by a value somebody typed into the console.

    || Mezcla la fila del proveedor con el entorno, y gana el entorno: un
    despliegue con gestión de secretos de verdad nunca queda sobreescrito en
    silencio por algo que alguien tipeó en la consola.
    """
    from app.foundation.secrets import SecretsCorrupted, decrypt

    env_value = _env_key(row.api_key_setting, settings)
    if env_value:
        return ResolvedProvider(
            id=row.id,
            label=row.label,
            wire=row.wire,
            base_url=row.base_url,
            enabled=row.enabled,
            note=row.note,
            api_key_setting=row.api_key_setting,
            api_key=env_value,
            api_key_hint=None,
            key_source="env",
        )

    stored: str | None = None
    if row.api_key_ciphertext:
        try:
            stored = decrypt(row.api_key_ciphertext)
        except SecretsCorrupted:
            # Unreadable is not usable: report it as no credential rather than
            # hand a provider a broken value.
            # || Ilegible no es usable: se reporta como sin credencial en vez de
            # pasarle un valor roto al proveedor.
            stored = None

    return ResolvedProvider(
        id=row.id,
        label=row.label,
        wire=row.wire,
        base_url=row.base_url,
        enabled=row.enabled,
        note=row.note,
        api_key_setting=row.api_key_setting,
        api_key=stored,
        api_key_hint=row.api_key_hint if stored else None,
        key_source="stored" if stored else "none",
    )


async def seed_if_empty(session: AsyncSession, settings: Settings) -> int:
    """Populate the tables from the code registry on first boot.

    Idempotent and additive: it inserts what is missing and never touches an
    existing row, so a human's edits (a hidden model, a renamed label, a
    stored credential) survive every restart. Returns how many rows it added.

    Seeding rather than requiring manual setup is what keeps a fresh install
    behaving exactly as it did when the catalog was an env var — the console
    becomes the place to change it, not a prerequisite for the service to work.

    || Llena las tablas desde el registro de código en el primer arranque.
    Idempotente y aditivo: inserta lo que falta y nunca toca una fila
    existente, así las ediciones de una persona (un modelo oculto, un label
    cambiado, una credencial guardada) sobreviven cada reinicio.
    """
    from app.foundation.llm.providers import SEED_PROVIDERS, supports_temperature_default

    added = 0

    for spec in SEED_PROVIDERS:
        # `MOONSHOT_BASE_URL` still wins for the provider that declares one, so
        # a deployment that already set it does not get the hard-coded default.
        # || `MOONSHOT_BASE_URL` sigue ganando para el proveedor que declara
        # uno, así un despliegue que ya lo puso no recibe el default fijo.
        base_url = spec.base_url
        if spec.id == "moonshot":
            base_url = str(getattr(settings, "MOONSHOT_BASE_URL", "") or "") or base_url

        result = await session.execute(
            pg_insert(ProviderRow)
            .values(
                id=spec.id,
                label=spec.label,
                wire=spec.wire,
                base_url=base_url,
                api_key_setting=spec.api_key_setting,
                enabled=True,
                note=spec.note or None,
            )
            .on_conflict_do_nothing(index_elements=[ProviderRow.id])
        )
        added += result.rowcount or 0

    for raw in settings.ANSWER_MODEL_CATALOG:
        provider_id, separator, model = str(raw).partition(":")
        if not separator or not model:
            log.warning("model_catalog_entry_malformed", entry=raw)
            continue
        if not any(spec.id == provider_id for spec in SEED_PROVIDERS):
            log.warning("model_catalog_unknown_provider", entry=raw, provider=provider_id)
            continue
        result = await session.execute(
            pg_insert(ProviderModelRow)
            .values(
                provider_id=provider_id,
                model=model,
                supports_temperature=supports_temperature_default(model),
                visible=True,
            )
            .on_conflict_do_nothing(constraint="uq_provider_models_pair")
        )
        added += result.rowcount or 0

    await session.commit()
    if added:
        log.info("providers_seeded", rows=added)
    return added


class ProviderRepository:
    """Reads and writes ``providers`` and ``provider_models``.

    || Lee y escribe ``providers`` y ``provider_models``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def providers(self) -> list[ProviderRow]:
        """Every provider row, ordered for a stable console. || Todas las filas."""
        result = await self._session.execute(select(ProviderRow).order_by(ProviderRow.id))
        return list(result.scalars())

    async def provider(self, provider_id: str) -> ProviderRow | None:
        result = await self._session.execute(
            select(ProviderRow).where(ProviderRow.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def models(self) -> list[ProviderModelRow]:
        result = await self._session.execute(
            select(ProviderModelRow).order_by(
                ProviderModelRow.provider_id, ProviderModelRow.model
            )
        )
        return list(result.scalars())

    async def model(self, provider_id: str, model: str) -> ProviderModelRow | None:
        result = await self._session.execute(
            select(ProviderModelRow).where(
                ProviderModelRow.provider_id == provider_id,
                ProviderModelRow.model == model,
            )
        )
        return result.scalar_one_or_none()

    async def update_provider(
        self,
        provider_id: str,
        *,
        label: str | None = None,
        base_url: str | None = None,
        enabled: bool | None = None,
        note: str | None = None,
    ) -> ProviderRow | None:
        """Update the non-secret fields of a provider. || Campos no secretos."""
        row = await self.provider(provider_id)
        if row is None:
            return None
        if label is not None:
            row.label = label
        if base_url is not None:
            row.base_url = base_url or None
        if enabled is not None:
            row.enabled = enabled
        if note is not None:
            row.note = note or None
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def set_api_key(self, provider_id: str, api_key: str) -> ProviderRow | None:
        """Store a credential as ciphertext, keeping only a hint in the clear.

        || Guarda una credencial como ciphertext, dejando en claro solo un hint.
        """
        from app.foundation.secrets import encrypt, hint

        row = await self.provider(provider_id)
        if row is None:
            return None
        row.api_key_ciphertext = encrypt(api_key)
        row.api_key_hint = hint(api_key)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def clear_api_key(self, provider_id: str) -> ProviderRow | None:
        """Forget a stored credential. || Olvida una credencial guardada."""
        row = await self.provider(provider_id)
        if row is None:
            return None
        row.api_key_ciphertext = None
        row.api_key_hint = None
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def upsert_model(
        self,
        provider_id: str,
        model: str,
        *,
        supports_temperature: bool = True,
        visible: bool = True,
    ) -> ProviderModelRow:
        """Add a model, or leave an existing one's curation alone.

        A refresh from the provider must not undo a human's decision to hide a
        model, so an existing row keeps its ``visible`` and its capability.

        || Agrega un modelo, o deja en paz la curaduría de uno existente: un
        refresh desde el proveedor no puede deshacer la decisión humana de
        ocultar un modelo.
        """
        statement = (
            pg_insert(ProviderModelRow)
            .values(
                provider_id=provider_id,
                model=model,
                supports_temperature=supports_temperature,
                visible=visible,
            )
            .on_conflict_do_nothing(constraint="uq_provider_models_pair")
        )
        await self._session.execute(statement)
        await self._session.commit()
        existing = await self.model(provider_id, model)
        assert existing is not None
        return existing

    async def upsert_models(
        self, provider_id: str, entries: list[tuple[str, bool, bool]]
    ) -> int:
        """Insert many models in ONE statement, skipping the ones already there.

        One statement and not a loop over ``upsert_model``: a refresh brings
        back everything a provider serves (OpenAI lists ~80 ids), and three
        round-trips per model against a database reached over a public proxy
        turns a listing into a request that times out. Measured: that is
        exactly what happened before this existed.

        Returns how many rows were actually inserted.

        || Un solo statement y no un loop sobre ``upsert_model``: un refresh
        trae todo lo que sirve un proveedor (OpenAI lista ~80 ids), y tres
        round-trips por modelo contra una base alcanzada por un proxy público
        convierte un listado en un request que expira. Medido: es exactamente
        lo que pasaba antes de que esto existiera.
        """
        if not entries:
            return 0

        statement = (
            pg_insert(ProviderModelRow)
            .values(
                [
                    {
                        "provider_id": provider_id,
                        "model": model,
                        "supports_temperature": supports_temperature,
                        "visible": visible,
                    }
                    for model, supports_temperature, visible in entries
                ]
            )
            .on_conflict_do_nothing(constraint="uq_provider_models_pair")
        )
        result = await self._session.execute(statement)
        await self._session.commit()
        return result.rowcount or 0

    async def update_model(
        self,
        provider_id: str,
        model: str,
        *,
        supports_temperature: bool | None = None,
        visible: bool | None = None,
    ) -> ProviderModelRow | None:
        row = await self.model(provider_id, model)
        if row is None:
            return None
        if supports_temperature is not None:
            row.supports_temperature = supports_temperature
        if visible is not None:
            row.visible = visible
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def delete_model(self, provider_id: str, model: str) -> bool:
        row = await self.model(provider_id, model)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True
