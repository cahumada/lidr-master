"""GET/PUT /config — the agent catalog and its per-agent overrides.

The console renders its "Agentes" screen from here instead of declaring the
graph a second time in TypeScript: the catalog, the privilege table and the
effective model all come from the service that runs them, so the screen cannot
describe a graph that no longer exists.

|| GET/PUT /config — el catálogo de agentes y sus overrides por agente. La
consola arma su pantalla "Agentes" desde acá en vez de declarar el grafo una
segunda vez en TypeScript: el catálogo, la tabla de privilegios y el modelo
vigente salen del servicio que los corre, así que la pantalla no puede describir
un grafo que ya no existe.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain.graph.catalog import AGENT_SPECS, AgentSpec, agent_spec, configurable_agent_keys
from app.domain.profiles import (
    AgentProfileRepository,
    AgentProfileRow,
    EffectiveAgentConfig,
    resolve_agent_config,
)
from app.foundation.llm.providers import (
    PROVIDER_SPECS,
    catalog_entry,
    is_available,
    parse_catalog,
    provider_spec,
)
from app.foundation.persistence.database import get_async_session

router = APIRouter(prefix="/config", tags=["config"])
log = structlog.get_logger()


class ConfigSources(BaseModel):
    """Where each effective value came from. || De dónde salió cada valor vigente."""

    provider: str = Field(description="'profile' or 'settings'. || 'profile' o 'settings'.")
    model: str = Field(description="'profile' or 'settings'. || 'profile' o 'settings'.")
    temperature: str = Field(
        description="'profile', 'settings', or 'unsupported' when the model rejects "
        "sampling parameters. || 'profile', 'settings', o 'unsupported' cuando el modelo "
        "rechaza los parámetros de sampling."
    )
    max_tokens: str
    persona: str = Field(description="'profile' or 'unset'. || 'profile' o 'unset'.")


class ProviderView(BaseModel):
    """One generation provider and whether it can be used. || Un proveedor y si se puede usar."""

    id: str
    label: str
    available: bool = Field(
        description="False when no API key is configured for it. "
        "|| False cuando no tiene clave configurada."
    )
    api_key_setting: str = Field(
        description="The setting that would make it available. || El setting que lo habilitaría."
    )
    note: str = ""


class ModelView(BaseModel):
    """One selectable model, with what it accepts. || Un modelo elegible, con lo que acepta."""

    provider: str
    model: str
    available: bool = Field(
        description="False when its provider has no key. || False si su proveedor no tiene clave."
    )
    supports_temperature: bool = Field(
        description="False for models that reject sampling parameters (current Claude "
        "models return 400). || False para modelos que rechazan los parámetros de sampling."
    )


class EffectiveConfigView(BaseModel):
    """What an LLM-driven agent runs with right now.

    || Con qué corre ahora mismo un agente que llama a un modelo.
    """

    provider: str
    model: str
    temperature: float | None = Field(
        default=None,
        description="Null when the model does not accept one. "
        "|| Null cuando el modelo no acepta una.",
    )
    max_tokens: int
    persona: str | None = None
    supports_temperature: bool
    provider_available: bool = Field(
        description="False when the effective provider has no key configured — the next "
        "answer would fail. || False cuando el proveedor vigente no tiene clave: la "
        "próxima respuesta fallaría."
    )
    sources: ConfigSources


class AgentConfigView(BaseModel):
    """One agent as the console shows it. || Un agente como lo muestra la consola."""

    key: str
    label: str
    role: str
    explanation: str
    kind: str = Field(description="'supervisor' | 'agent' | 'gate'.")
    tools: list[str] = Field(
        default_factory=list,
        description="Tools it may call, from the privilege table. "
        "|| Herramientas que puede llamar, de la tabla de privilegios.",
    )
    llm_driven: bool = Field(
        description="False for the deterministic agents — they have no model to pick. "
        "|| False para los agentes deterministas: no tienen modelo que elegir."
    )
    configurable: bool = Field(
        description="Whether a profile changes this agent's behaviour. "
        "|| Si un perfil cambia el comportamiento de este agente."
    )
    config_source: str | None = Field(
        default=None,
        description="The setting that supplies its defaults. || El setting que da sus defaults.",
    )
    effective: EffectiveConfigView | None = Field(
        default=None,
        description="Present only for LLM-driven agents. || Presente solo para agentes con modelo.",
    )


class ServiceConfigResponse(BaseModel):
    """Response of ``GET /config``. || Respuesta de ``GET /config``."""

    providers: list[ProviderView] = Field(
        description="Every generation provider the service knows, available or not. "
        "|| Todos los proveedores de generación que el servicio conoce."
    )
    models: list[ModelView] = Field(
        description="Models the console may offer per agent, with their provider. "
        "|| Modelos que la consola puede ofrecer, con su proveedor."
    )
    persona_max_chars: int
    agents: list[AgentConfigView]


class AgentProfileUpdate(BaseModel):
    """Body of ``PUT /config/agents/{agent_key}``.

    Every field is optional and ``null`` means "back to the service default" —
    a cleared field in the form has to be a real operation, not a value the
    API has no way to express.

    || Body de ``PUT /config/agents/{agent_key}``. Todos los campos son
    opcionales y ``null`` significa "volver al default del servicio".
    """

    persona: str | None = Field(
        default=None,
        description="Appended to the system prompt, after the rules and subordinate to them. "
        "|| Se appendea al system prompt, después de las reglas y subordinado a ellas.",
    )
    provider: str | None = Field(
        default=None,
        description="Must be sent together with `model` and match a catalog entry. "
        "|| Va junto con `model` y tiene que coincidir con una entrada del catálogo.",
    )
    model: str | None = Field(
        default=None, description="Must be in the catalog. || Tiene que estar en el catálogo."
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)


def _view(spec: AgentSpec, profile: AgentProfileRow | None, settings: Settings) -> AgentConfigView:
    configurable = spec.key in configurable_agent_keys()
    effective: EffectiveConfigView | None = None
    if spec.llm_driven:
        merged: EffectiveAgentConfig = resolve_agent_config(profile, settings)
        effective = EffectiveConfigView(
            provider=merged.provider,
            model=merged.model,
            temperature=merged.temperature,
            max_tokens=merged.max_tokens,
            persona=merged.persona,
            supports_temperature=merged.supports_temperature,
            provider_available=is_available(merged.provider, settings),
            sources=ConfigSources(**merged.sources),
        )
    return AgentConfigView(
        key=spec.key,
        label=spec.label,
        role=spec.role,
        explanation=spec.explanation,
        kind=spec.kind,
        tools=spec.tools,
        llm_driven=spec.llm_driven,
        configurable=configurable,
        config_source=spec.config_source,
        effective=effective,
    )


def _require_configurable(agent_key: str) -> AgentSpec:
    spec = agent_spec(agent_key)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent named {agent_key!r}. || No existe un agente {agent_key!r}.",
        )
    if agent_key not in configurable_agent_keys():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Agent {agent_key!r} is deterministic: it calls no model, so a persona or "
                "a model override would not change what it does. Rejected instead of stored "
                "and silently ignored. || El agente es determinista: no llama a ningún "
                "modelo, así que una persona o un modelo no cambiarían lo que hace."
            ),
        )
    return spec


def _validated_pair(
    provider: str | None, model: str | None, settings: Settings
) -> tuple[str | None, str | None]:
    """Validate the (provider, model) pair, or explain why it cannot be used.

    The pair is validated together and stored together. A model with no
    provider is accepted only when the service default provider serves it —
    otherwise "gpt-4o with the Anthropic default" would be stored as a
    combination nobody can run.

    || Valida el par (proveedor, modelo) junto, y junto se guarda. Un modelo
    sin proveedor se acepta solo si el proveedor default lo sirve — si no,
    quedaría guardada una combinación que nadie puede correr.
    """
    if provider is None and model is None:
        return None, None

    if model is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "provider was sent without a model; the pair travels together. "
                "|| Se mandó el proveedor sin modelo; el par va junto."
            ),
        )

    effective_provider = provider or settings.ANSWER_PROVIDER
    entry = catalog_entry(effective_provider, model, settings)
    if entry is None:
        offered = ", ".join(f"{e.provider}:{e.model}" for e in parse_catalog(settings))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{effective_provider}:{model} is not in the catalog ({offered}). "
                "|| Ese par proveedor:modelo no está en el catálogo."
            ),
        )

    if not is_available(effective_provider, settings):
        spec = provider_spec(effective_provider)
        setting = spec.api_key_setting if spec else "its API key"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{effective_provider} has no API key configured ({setting}), so this model "
                "would fail at answer time. Rejected here instead. "
                f"|| {effective_provider} no tiene clave configurada ({setting}), así que "
                "este modelo fallaría al responder. Se rechaza acá."
            ),
        )

    return effective_provider, model


@router.get("", response_model=ServiceConfigResponse)
async def read_config(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> ServiceConfigResponse:
    """The agent catalog with each agent's effective configuration.

    || El catálogo de agentes con la configuración vigente de cada uno.
    """
    settings = get_settings()
    profiles = await AgentProfileRepository(session).all()
    return ServiceConfigResponse(
        providers=[
            ProviderView(
                id=spec.id,
                label=spec.label,
                available=is_available(spec.id, settings),
                api_key_setting=spec.api_key_setting,
                note=spec.docs_note,
            )
            for spec in PROVIDER_SPECS
        ],
        models=[
            ModelView(
                provider=entry.provider,
                model=entry.model,
                available=is_available(entry.provider, settings),
                supports_temperature=entry.supports_temperature,
            )
            for entry in parse_catalog(settings)
        ],
        persona_max_chars=settings.AGENT_PERSONA_MAX_CHARS,
        agents=[_view(spec, profiles.get(spec.key), settings) for spec in AGENT_SPECS],
    )


@router.put("/agents/{agent_key}", response_model=AgentConfigView)
async def update_agent_profile(
    agent_key: str,
    body: AgentProfileUpdate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Replace ``agent_key``'s profile. Null fields fall back to the defaults.

    || Reemplaza el perfil de ``agent_key``. Los campos nulos caen a los defaults.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)

    persona = (body.persona or "").strip() or None
    if persona and len(persona) > settings.AGENT_PERSONA_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"persona is {len(persona)} chars, over the "
                f"{settings.AGENT_PERSONA_MAX_CHARS} cap. || La persona excede el tope."
            ),
        )
    provider, model = _validated_pair(body.provider, body.model, settings)

    profile = await AgentProfileRepository(session).upsert(
        agent_key,
        persona=persona,
        provider=provider,
        model=model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    log.info(
        "agent_profile_updated",
        agent=agent_key,
        provider=provider,
        model=model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        persona_chars=len(persona or ""),
    )
    return _view(spec, profile, settings)


@router.delete("/agents/{agent_key}", response_model=AgentConfigView)
async def delete_agent_profile(
    agent_key: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Drop ``agent_key``'s profile so it runs on the service defaults again.

    || Borra el perfil de ``agent_key`` para que vuelva a correr con los defaults.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)
    deleted = await AgentProfileRepository(session).delete(agent_key)
    log.info("agent_profile_deleted", agent=agent_key, existed=deleted)
    return _view(spec, None, settings)
