"""Named per-agent profiles: persona, model, temperature, token cap.

In a table and not in a file: the deployment's filesystem is ephemeral
(Railway rebuilds the container on every deploy), so a persona edited in the
console would survive until the next push and then quietly revert. The corpus
already needs Postgres, so this costs one small table and no new dependency.

Every knob is nullable and an absent knob means "use the service default" —
the same semantics as the course's `config_payload`, which sends only the keys
that are set. That is what makes "clear the field to go back to the default" a
real operation instead of a magic sentinel value.

A configurable agent may have several named presets (``Conservador``,
``Exhaustivo``). At most one is the default; a run may pick another by id.

|| Perfiles nombrados por agente: persona, modelo, temperatura, tope de tokens.

En una tabla y no en un archivo: el filesystem del despliegue es efímero
(Railway reconstruye el contenedor en cada deploy), así que una persona editada
en la consola sobreviviría hasta el próximo push y después volvería sola al
default sin avisar. El corpus ya necesita Postgres, así que esto cuesta una
tabla chica y ninguna dependencia nueva.

Cada knob es nullable y un knob ausente significa "usar el default del
servicio" — la misma semántica que el `config_payload` del curso.

Un agente configurable puede tener varios presets nombrados. A lo sumo uno es
el default; una corrida puede pedir otro por id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Settings
from app.domain.graph.catalog import SYNTHESIZER_AGENT
from app.foundation.persistence.database import Base

DEFAULT_PROFILE_NAME = "Default"
PROFILE_NAME_MAX_CHARS = 64


class ProfileResolutionError(ValueError):
    """A requested profile cannot be used for this run.

    The routers translate this to HTTP 422. It is a domain error, not a
    missing row the caller should treat as "fall back to settings" — picking
    an id that does not exist is a bad request.

    || Un perfil pedido no se puede usar en esta corrida. Los routers lo
    traducen a HTTP 422: pedir un id que no existe es un request malo, no un
    fallback silencioso a Settings.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ProfileValidationError(ValueError):
    """A write is structurally invalid (blank name, duplicate name).

    || Una escritura es inválida de forma (nombre vacío, nombre duplicado).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AgentProfileRow(Base):
    """One named preset of an agent's overrides.

    || Un preset nombrado de los overrides de un agente.
    """

    __tablename__ = "agent_profiles"
    __table_args__ = (
        Index(
            "uq_agent_profiles_agent_key_name",
            "agent_key",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(
        String(PROFILE_NAME_MAX_CHARS), nullable=False, default=DEFAULT_PROFILE_NAME
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    persona: Mapped[str | None] = mapped_column(Text)
    guardrails: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_tokens: Mapped[int | None] = mapped_column(Integer)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


@dataclass(frozen=True)
class EffectiveAgentConfig:
    """What the agent will actually run with, and where each value came from.

    ``sources`` matters for the console: "temperatura 0.0" reads very
    differently when it is the service default than when somebody set it.

    ``temperature`` is ``None`` when the chosen model does not accept one —
    current Claude models reject sampling parameters with a 400, so "no
    temperature" is a real state and not a missing value.

    || Con qué va a correr realmente el agente, y de dónde salió cada valor.
    ``temperature`` es ``None`` cuando el modelo elegido no la acepta — los
    modelos Claude actuales rechazan los parámetros de sampling con un 400,
    así que "sin temperatura" es un estado real y no un valor faltante.
    """

    provider: str
    model: str
    temperature: float | None
    max_tokens: int
    persona: str | None
    guardrails: str | None
    supports_temperature: bool
    sources: dict[str, str]


def normalize_profile_name(name: str) -> str:
    """Strip and reject a blank name. || Recorta y rechaza un nombre vacío."""
    cleaned = name.strip()
    if not cleaned:
        raise ProfileValidationError(
            "profile name is empty. || El nombre del perfil está vacío."
        )
    if len(cleaned) > PROFILE_NAME_MAX_CHARS:
        raise ProfileValidationError(
            f"profile name is {len(cleaned)} chars, over the {PROFILE_NAME_MAX_CHARS} cap. "
            "|| El nombre del perfil excede el tope."
        )
    return cleaned


def assert_name_available(
    existing: list[AgentProfileRow],
    name: str,
    *,
    exclude_id: str | None = None,
) -> None:
    """Refuse a case-insensitive duplicate name on the same agent.

    || Rechaza un nombre duplicado (sin distinguir mayúsculas) en el mismo agente.
    """
    wanted = name.casefold()
    for row in existing:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if row.name.casefold() == wanted:
            raise ProfileValidationError(
                f"a profile named {name!r} already exists for this agent. "
                "|| Ya existe un perfil con ese nombre en este agente."
            )


def pick_promoted_default(remaining: list[AgentProfileRow]) -> AgentProfileRow | None:
    """The profile that becomes default after the current default is deleted.

    Most recently updated wins; an empty list means the agent falls back to
    Settings — no invented row.

    || El perfil que pasa a default al borrar el vigente. Gana el más
    recientemente actualizado; una lista vacía deja al agente en Settings.
    """
    if not remaining:
        return None
    return max(remaining, key=lambda row: row.updated_at or datetime.min.replace(tzinfo=UTC))


def resolve_agent_config(
    profile: AgentProfileRow | None,
    settings: Settings,
    *,
    supports_temperature: bool | None = None,
) -> EffectiveAgentConfig:
    """Merge an agent's overrides over the service defaults.

    ``supports_temperature`` comes from the model's row when the database has
    one; ``None`` falls back to what the code knows, which is what a model
    nobody has recorded yet gets.

    || Mezcla los overrides de un agente sobre los defaults del servicio.
    ``supports_temperature`` viene de la fila del modelo cuando la base tiene
    una; ``None`` cae a lo que sabe el código, que es lo que le toca a un
    modelo que nadie registró todavía.
    """
    from app.foundation.llm.providers import supports_temperature_default

    provider = getattr(profile, "provider", None)
    model = getattr(profile, "model", None)
    temperature = getattr(profile, "temperature", None)
    max_tokens = getattr(profile, "max_tokens", None)
    persona = getattr(profile, "persona", None)
    guardrails = getattr(profile, "guardrails", None)

    # The pair moves together: a stored model with no stored provider would
    # otherwise be read against the default provider, which may not serve it.
    # || El par se mueve junto: un modelo guardado sin proveedor guardado se
    # leería contra el proveedor default, que puede no servirlo.
    effective_model = model or settings.ANSWER_MODEL
    effective_provider = provider or (settings.ANSWER_PROVIDER if not model else provider)
    if not effective_provider:
        effective_provider = settings.ANSWER_PROVIDER

    accepts_temperature = (
        supports_temperature_default(effective_model)
        if supports_temperature is None
        else supports_temperature
    )
    if not accepts_temperature:
        effective_temperature = None
        temperature_source = "unsupported"
    elif temperature is None:
        effective_temperature = settings.ANSWER_TEMPERATURE
        temperature_source = "settings"
    else:
        effective_temperature = temperature
        temperature_source = "profile"

    return EffectiveAgentConfig(
        provider=effective_provider,
        model=effective_model,
        temperature=effective_temperature,
        max_tokens=max_tokens or settings.ANSWER_MAX_TOKENS,
        persona=persona or None,
        guardrails=guardrails or None,
        supports_temperature=accepts_temperature,
        sources={
            "provider": "profile" if provider else "settings",
            "model": "profile" if model else "settings",
            "temperature": temperature_source,
            "max_tokens": "profile" if max_tokens else "settings",
            "persona": "profile" if persona else "unset",
            "guardrails": "profile" if guardrails else "unset",
        },
    )


async def load_synthesizer_profile(
    session: AsyncSession, *, profile_id: str | None = None
) -> AgentProfileRow | None:
    """The synthesizer profile this run should use, or ``None`` for Settings.

    An explicit id that is missing or belongs to another agent is an error,
    not a silent fallback: the caller asked for a specific voice.

    || El perfil del sintetizador que esta corrida debe usar, o ``None`` para
    Settings. Un id explícito que no existe o es de otro agente es un error,
    no un fallback silencioso: el llamador pidió una voz puntual.
    """
    repo = AgentProfileRepository(session)
    if profile_id:
        profile = await repo.get_by_id(profile_id)
        if profile is None:
            raise ProfileResolutionError(
                f"No profile {profile_id!r}. || No existe el perfil {profile_id!r}."
            )
        if profile.agent_key != SYNTHESIZER_AGENT:
            raise ProfileResolutionError(
                f"profile {profile_id!r} belongs to {profile.agent_key!r}, not "
                f"{SYNTHESIZER_AGENT!r}. || El perfil no es del sintetizador."
            )
        return profile
    return await repo.default_for(SYNTHESIZER_AGENT)


async def synthesizer_runtime(
    session: AsyncSession,
    settings: Settings,
    *,
    profile_id: str | None = None,
) -> tuple[Any, str | None, str | None]:
    """The LLM, persona and operator guardrails the synthesizer profile asks for.

    The single seam every synthesis path goes through — ``POST /answer``,
    ``POST /answer/agentic`` and the background runner — so a persona
    configured in the console cannot apply to one of them and not the others.
    The graph receives both through its config instead of letting the agent
    read the database, which is what keeps the agent testable without one.

    ``profile_id`` selects a named preset for this run; absent means the
    default, and no default means the service settings.

    || El único punto por el que pasan todos los caminos de síntesis, así una
    persona configurada en la consola no puede aplicar a uno y no a los otros.
    ``profile_id`` elige un preset para esta corrida; ausente = default.
    """
    from app.foundation.llm.providers import build_llm_for

    profile = await load_synthesizer_profile(session, profile_id=profile_id)
    effective = await _effective_for_profile(profile, session, settings)
    resolved = await resolved_provider(session, settings, effective.provider)
    llm = build_llm_for(
        resolved,
        effective.model,
        max_tokens=effective.max_tokens,
        temperature=effective.temperature,
        supports_temperature=effective.supports_temperature,
    )
    return llm, effective.persona, effective.guardrails


async def resolved_provider(session: AsyncSession, settings: Settings, provider_id: str):
    """The provider row for ``provider_id``, with its credential resolved.

    || La fila del proveedor, con su credencial resuelta.
    """
    from app.domain.providers_store import ProviderRepository, resolve_provider
    from app.foundation.llm.providers import LLMProviderError

    row = await ProviderRepository(session).provider(provider_id)
    if row is None:
        raise LLMProviderError(
            f"provider {provider_id!r} is not configured in this service "
            f"|| el proveedor {provider_id!r} no está configurado en este servicio"
        )
    return resolve_provider(row, settings)


async def _effective_for_profile(
    profile: AgentProfileRow | None, session: AsyncSession, settings: Settings
) -> EffectiveAgentConfig:
    from app.domain.providers_store import ProviderRepository

    provisional = resolve_agent_config(profile, settings)
    row = await ProviderRepository(session).model(provisional.provider, provisional.model)
    return resolve_agent_config(
        profile,
        settings,
        supports_temperature=row.supports_temperature if row else None,
    )


async def effective_config_for(
    agent_key: str, session: AsyncSession, settings: Settings
) -> EffectiveAgentConfig:
    """Load ``agent_key``'s default profile and merge it over the defaults.

    || Carga el perfil default de ``agent_key`` y lo mezcla sobre los defaults.
    """
    profile = await AgentProfileRepository(session).default_for(agent_key)
    return await _effective_for_profile(profile, session, settings)


class AgentProfileRepository:
    """Reads and writes named ``agent_profiles``. || Lee y escribe perfiles nombrados."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, profile_id: str) -> AgentProfileRow | None:
        """The profile with this id, or ``None``. || El perfil con este id, o ``None``."""
        result = await self._session.execute(
            select(AgentProfileRow).where(AgentProfileRow.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_for(self, agent_key: str) -> list[AgentProfileRow]:
        """Every named profile of ``agent_key``. || Todos los perfiles de ``agent_key``."""
        result = await self._session.execute(
            select(AgentProfileRow)
            .where(AgentProfileRow.agent_key == agent_key)
            .order_by(AgentProfileRow.name)
        )
        return list(result.scalars())

    async def default_for(self, agent_key: str) -> AgentProfileRow | None:
        """The default profile of ``agent_key``, or ``None``.

        || El perfil default de ``agent_key``, o ``None``.
        """
        result = await self._session.execute(
            select(AgentProfileRow).where(
                AgentProfileRow.agent_key == agent_key,
                AgentProfileRow.is_default.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def all(self) -> dict[str, list[AgentProfileRow]]:
        """Every stored profile, grouped by agent. || Todos los perfiles, por agente."""
        result = await self._session.execute(select(AgentProfileRow))
        grouped: dict[str, list[AgentProfileRow]] = {}
        for row in result.scalars():
            grouped.setdefault(row.agent_key, []).append(row)
        return grouped

    async def create(
        self,
        agent_key: str,
        *,
        name: str,
        is_default: bool,
        persona: str | None,
        guardrails: str | None,
        provider: str | None,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AgentProfileRow:
        """Insert a named profile, enforcing unique name and a single default.

        The first profile of an agent becomes the default even if the caller
        did not ask: zero defaults and one unused preset is a trap.

        || Inserta un perfil nombrado. El primero de un agente pasa a default
        aunque no se pida: cero defaults y un preset sin usar es una trampa.
        """
        name = normalize_profile_name(name)
        existing = await self.list_for(agent_key)
        assert_name_available(existing, name)
        if not existing:
            is_default = True

        row = AgentProfileRow(
            id=str(uuid4()),
            agent_key=agent_key,
            name=name,
            is_default=is_default,
            persona=persona,
            guardrails=guardrails,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if is_default:
            await self._clear_defaults(agent_key)
            row.is_default = True
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def update(
        self,
        profile_id: str,
        *,
        name: str,
        is_default: bool,
        persona: str | None,
        guardrails: str | None,
        provider: str | None,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AgentProfileRow | None:
        """Replace a named profile. ``None`` if the id does not exist.

        || Reemplaza un perfil nombrado. ``None`` si el id no existe.
        """
        row = await self.get_by_id(profile_id)
        if row is None:
            return None
        name = normalize_profile_name(name)
        siblings = await self.list_for(row.agent_key)
        assert_name_available(siblings, name, exclude_id=row.id)

        was_default = row.is_default
        row.name = name
        row.persona = persona
        row.guardrails = guardrails
        row.provider = provider
        row.model = model
        row.temperature = temperature
        row.max_tokens = max_tokens
        if is_default:
            await self._clear_defaults(row.agent_key)
            row.is_default = True
        else:
            row.is_default = False
            if was_default:
                await self._session.flush()
                remaining = [item for item in await self.list_for(row.agent_key) if item.id != row.id]
                promoted = pick_promoted_default(remaining)
                if promoted is not None:
                    promoted.is_default = True
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def delete_one(self, profile_id: str) -> AgentProfileRow | None:
        """Delete one profile and promote a sibling if it was the default.

        Returns the deleted row (detached) so the caller can see which agent
        it belonged to; ``None`` if the id was unknown.

        || Borra un perfil y promociona a un hermano si era el default.
        """
        row = await self.get_by_id(profile_id)
        if row is None:
            return None
        agent_key = row.agent_key
        was_default = row.is_default
        await self._session.delete(row)
        if was_default:
            remaining = [item for item in await self.list_for(agent_key) if item.id != row.id]
            promoted = pick_promoted_default(remaining)
            if promoted is not None:
                promoted.is_default = True
        await self._session.commit()
        return row

    async def upsert(
        self,
        agent_key: str,
        *,
        persona: str | None,
        guardrails: str | None,
        provider: str | None,
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AgentProfileRow:
        """Alias: write the default profile, creating ``Default`` if needed.

        Kept so ``PUT /config/agents/{key}`` stays a real operation — it
        updates the default named profile instead of a second anonymous row.

        || Alias: escribe el perfil default, creando ``Default`` si hace falta.
        """
        current = await self.default_for(agent_key)
        if current is None:
            return await self.create(
                agent_key,
                name=DEFAULT_PROFILE_NAME,
                is_default=True,
                persona=persona,
                guardrails=guardrails,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        current.persona = persona
        current.guardrails = guardrails
        current.provider = provider
        current.model = model
        current.temperature = temperature
        current.max_tokens = max_tokens
        await self._session.commit()
        await self._session.refresh(current)
        return current

    async def delete(self, agent_key: str) -> bool:
        """Drop every profile of ``agent_key``, so the agent falls back to Settings.

        The anonymous ``DELETE /config/agents/{key}`` means "back to the
        service defaults", which with named profiles is all of them, not just
        the default row.

        || Borra todos los perfiles de ``agent_key``, así el agente cae a Settings.
        """
        rows = await self.list_for(agent_key)
        if not rows:
            return False
        for row in rows:
            await self._session.delete(row)
        await self._session.commit()
        return True

    async def _clear_defaults(self, agent_key: str) -> None:
        await self._session.execute(
            update(AgentProfileRow)
            .where(AgentProfileRow.agent_key == agent_key)
            .values(is_default=False)
        )
