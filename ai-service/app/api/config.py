"""/config — providers, their models, and the per-agent overrides.

The console renders its "Agentes" screen from here instead of declaring the
graph a second time in TypeScript: the catalog, the privilege table and the
effective model all come from the service that runs them, so the screen cannot
describe a graph that no longer exists.

Providers and models are database rows, so adding a model — or a whole
provider that speaks an implemented wire — is a write and not a deploy.

**On credentials.** `PUT /providers/{id}/key` is write-only by construction:
no endpoint in this file returns a key, decrypted or otherwise. What comes
back is `key_source` ("env" | "stored" | "none") and a four-character hint, so
an operator can tell WHICH key is loaded and WHERE to change it without the
key being readable through the API. An environment variable always wins over a
stored one, so a deployment using real secret management is never silently
overridden from the console.

|| /config — proveedores, sus modelos, y los overrides por agente. Los
proveedores y modelos son filas, así que agregar un modelo —o un proveedor
entero que hable un wire implementado— es una escritura y no un deploy.

**Sobre las credenciales.** `PUT /providers/{id}/key` es write-only por
construcción: ningún endpoint de este archivo devuelve una clave. Lo que vuelve
es `key_source` y un hint de cuatro caracteres, para saber CUÁL clave está
cargada y DÓNDE cambiarla sin que la clave sea legible por la API. Una variable
de entorno siempre le gana a una guardada.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.domain.graph.catalog import (
    AGENT_SPECS,
    AgentSpec,
    agent_spec,
    configurable_agent_keys,
    graph_flow,
    tool_catalog,
)
from app.domain.graph.inspector import (
    GUARDRAILS_TEMPLATE,
    PERSONA_TEMPLATE,
    base_system_prompt,
    compose_system_prompt,
    system_guardrails_view,
)
from app.domain.profiles import (
    AgentProfileRepository,
    AgentProfileRow,
    EffectiveAgentConfig,
    ProfileValidationError,
    resolve_agent_config,
)
from app.domain.providers_store import (
    ProviderModelRow,
    ProviderRepository,
    ResolvedProvider,
    resolve_provider,
)
from app.foundation.llm.providers import (
    WIRE_LABELS,
    LLMProviderError,
    list_provider_models,
    supports_temperature_default,
)
from app.foundation.persistence.database import get_async_session
from app.foundation.secrets import is_enabled as secrets_enabled

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
    guardrails: str = Field(description="'profile' or 'unset'. || 'profile' o 'unset'.")


class SystemGuardrailView(BaseModel):
    """One grounding rule the operator can see and cannot turn off.

    || Una regla de grounding que el operador ve y no puede apagar.
    """

    id: str
    kind: str = Field(description="'prompt' or 'code'. || 'prompt' o 'code'.")
    title: str
    description: str


class ToolCatalogView(BaseModel):
    """One tool the privilege table knows. || Una tool que conoce la tabla de privilegios."""

    name: str
    description: str
    granted_to: list[str]
    used_by: list[str]


class ProviderView(BaseModel):
    """One generation provider, as the console shows it.

    Carries NO credential. ``key_source`` and ``api_key_hint`` are what an
    operator needs to know which key is loaded and where to change it; the key
    itself is never returned by any endpoint.

    || Un proveedor de generación, como lo muestra la consola. NO lleva
    credencial: ``key_source`` y ``api_key_hint`` son lo que necesita quien
    opera para saber cuál clave está cargada y dónde cambiarla.
    """

    id: str
    label: str
    wire: str = Field(description="Which adapter talks to it. || Qué adaptador le habla.")
    wire_label: str
    base_url: str | None = None
    enabled: bool
    available: bool = Field(
        description="Enabled AND holding a credential. || Habilitado Y con credencial."
    )
    api_key_setting: str | None = Field(
        default=None,
        description="The environment variable that overrides a stored key. "
        "|| La variable de entorno que le gana a una clave guardada.",
    )
    key_source: str = Field(
        description="'env' (an environment variable), 'stored' (encrypted in the database), "
        "or 'none'. || 'env', 'stored' (cifrada en la base), o 'none'."
    )
    api_key_hint: str | None = Field(
        default=None,
        description="Last four characters of a STORED key, so two keys can be told apart. "
        "Never the key. || Últimos cuatro caracteres de una clave GUARDADA. Nunca la clave.",
    )
    model_count: int = 0
    note: str | None = None


class ModelView(BaseModel):
    """One selectable model, with what it accepts. || Un modelo elegible, con lo que acepta."""

    provider: str
    model: str
    available: bool = Field(
        description="False when its provider has no credential or is disabled. "
        "|| False si su proveedor no tiene credencial o está deshabilitado."
    )
    supports_temperature: bool = Field(
        description="False for models that reject sampling parameters (current Claude "
        "models return 400). || False para modelos que rechazan los parámetros de sampling."
    )
    visible: bool = Field(
        description="Hidden models stay stored so a refresh does not re-offer them. "
        "|| Los ocultos quedan guardados para que un refresh no los vuelva a ofrecer."
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
    guardrails: str | None = None
    supports_temperature: bool
    provider_available: bool = Field(
        description="False when the effective provider has no key configured — the next "
        "answer would fail. || False cuando el proveedor vigente no tiene clave: la "
        "próxima respuesta fallaría."
    )
    sources: ConfigSources


class NamedProfileView(BaseModel):
    """One named preset of a configurable agent. || Un preset nombrado de un agente configurable."""

    id: str
    name: str
    is_default: bool
    persona: str | None = None
    guardrails: str | None = None
    composed_system_prompt: str = Field(
        description="Base prompt plus this profile's persona and operator guardrails. "
        "|| Prompt base más la persona y los guardrails de este perfil."
    )
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    effective: EffectiveConfigView


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
    tools_used: list[str] = Field(
        default_factory=list,
        description="Tools this node actually calls. || Herramientas que este nodo llama.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Rendered answer/v1 system prompt without operator extras. "
        "Present on the synthesizer. || System prompt base; solo el sintetizador.",
    )
    system_guardrails: list[SystemGuardrailView] = Field(
        default_factory=list,
        description="Prompt rules plus the code grounding check. Not writable. "
        "|| Reglas del prompt más el chequeo de código. No se editan.",
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
        description="The default profile in force, or settings if none. "
        "Present only for LLM-driven agents. || El perfil default vigente, o settings.",
    )
    profiles: list[NamedProfileView] = Field(
        default_factory=list,
        description="Named presets. Empty for deterministic agents. "
        "|| Presets nombrados. Vacío en los deterministas.",
    )


class NodeExampleView(BaseModel):
    """What a node receives and leaves for the worked example question.

    ``caveat`` marks what only illustrates the node instead of being what the
    code deterministically produces — the synthesizer writes with a model, and
    the retrieved documents depend on the loaded corpus.

    || Qué recibe y qué deja un nodo para la pregunta de ejemplo. ``caveat``
    marca lo que solo ilustra, en vez de ser lo que el código produce siempre.
    """

    receives: str
    leaves: str
    detail: list[str] = Field(
        default_factory=list,
        description="Literal values shown verbatim: sub-queries, document ids. "
        "|| Valores literales que se muestran tal cual: subconsultas, ids.",
    )
    caveat: str | None = Field(
        default=None,
        description="Present when the example illustrates rather than asserts. "
        "|| Presente cuando el ejemplo ilustra en vez de afirmar.",
    )


class FlowExampleView(BaseModel):
    """The one question the flow screen walks through every node.

    || La pregunta que la pantalla de flujo recorre por todos los nodos.
    """

    question: str
    source: str = Field(
        description="Where the question comes from. || De dónde sale la pregunta."
    )
    note: str


class FlowNodeView(BaseModel):
    """One node of the answer graph, as the flow screen draws it."""

    key: str
    label: str
    kind: str
    role: str
    explanation: str
    llm_driven: bool
    tools: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    example: NodeExampleView


class FlowEdgeView(BaseModel):
    """One connector the compiled graph actually has. || Un conector que el grafo compilado tiene."""

    source: str
    target: str


class GraphFlowView(BaseModel):
    """Topology served so the console does not declare the graph again.

    || Topología servida para que la consola no declare el grafo otra vez.
    """

    nodes: list[FlowNodeView]
    edges: list[FlowEdgeView]
    ladder: list[str] = Field(
        description="The orchestrator's fallback order. || La escalera de fallback del orquestador."
    )
    example: FlowExampleView = Field(
        description="One real question walked through every node. "
        "|| Una pregunta real recorrida por todos los nodos."
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
    guardrails_max_chars: int = Field(
        description="Same cap as persona: operator extras share one budget. "
        "|| El mismo tope que persona: los extras de operador comparten presupuesto."
    )
    persona_template: str = Field(
        description="Suggested voice for a senior insurance analyst. "
        "|| Voz sugerida de un analista funcional senior de seguros."
    )
    guardrails_template: str = Field(
        description="Suggested extra operator constraints. "
        "|| Restricciones extra de operador sugeridas."
    )
    tools: list[ToolCatalogView] = Field(
        default_factory=list,
        description="Every tool the privilege table knows. "
        "|| Todas las tools que conoce la tabla de privilegios.",
    )
    agents: list[AgentConfigView]
    credential_storage_enabled: bool = Field(
        description="False when SECRETS_KEY is unset: credentials cannot be stored, and "
        "the console says so instead of offering a form that would fail. "
        "|| False cuando SECRETS_KEY no está definida: no se pueden guardar credenciales."
    )
    wires: dict[str, str] = Field(
        default_factory=dict,
        description="The wire formats this service implements, for adding a provider. "
        "|| Los formatos de wire que este servicio implementa.",
    )
    flow: GraphFlowView = Field(
        description="Compiled-graph topology for the flow screen. "
        "|| Topología del grafo compilado, para la pantalla de flujo.",
    )


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
    guardrails: str | None = Field(
        default=None,
        description="Extra operator constraints, appended after the persona. "
        "|| Restricciones extra de operador, después de la persona.",
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


class NamedProfileWrite(BaseModel):
    """Body of create/update for a named profile. || Body de alta/edición de un perfil nombrado."""

    name: str = Field(
        min_length=1,
        max_length=64,
        description="Unique among this agent's profiles. || Único entre los perfiles de este agente.",
    )
    is_default: bool = False
    persona: str | None = Field(default=None)
    guardrails: str | None = Field(default=None)
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)


def _effective_view(
    profile: AgentProfileRow | None,
    settings: Settings,
    resolved: dict[str, ResolvedProvider],
    capabilities: dict[tuple[str, str], bool],
) -> EffectiveConfigView:
    provisional: EffectiveAgentConfig = resolve_agent_config(profile, settings)
    merged = resolve_agent_config(
        profile,
        settings,
        supports_temperature=capabilities.get((provisional.provider, provisional.model)),
    )
    provider = resolved.get(merged.provider)
    return EffectiveConfigView(
        provider=merged.provider,
        model=merged.model,
        temperature=merged.temperature,
        max_tokens=merged.max_tokens,
        persona=merged.persona,
        guardrails=merged.guardrails,
        supports_temperature=merged.supports_temperature,
        provider_available=bool(provider and provider.available),
        sources=ConfigSources(**merged.sources),
    )


def _named_profile_view(
    row: AgentProfileRow,
    settings: Settings,
    resolved: dict[str, ResolvedProvider],
    capabilities: dict[tuple[str, str], bool],
) -> NamedProfileView:
    return NamedProfileView(
        id=row.id,
        name=row.name,
        is_default=row.is_default,
        persona=row.persona,
        guardrails=row.guardrails,
        composed_system_prompt=compose_system_prompt(
            persona=row.persona, guardrails=row.guardrails
        ),
        provider=row.provider,
        model=row.model,
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        effective=_effective_view(row, settings, resolved, capabilities),
    )


def _agent_view(
    spec: AgentSpec,
    profiles: list[AgentProfileRow],
    settings: Settings,
    resolved: dict[str, ResolvedProvider],
    capabilities: dict[tuple[str, str], bool],
) -> AgentConfigView:
    configurable = spec.key in configurable_agent_keys()
    default = next((row for row in profiles if row.is_default), None)
    effective: EffectiveConfigView | None = None
    named: list[NamedProfileView] = []
    if spec.llm_driven:
        effective = _effective_view(default, settings, resolved, capabilities)
        named = [_named_profile_view(row, settings, resolved, capabilities) for row in profiles]
    return AgentConfigView(
        key=spec.key,
        label=spec.label,
        role=spec.role,
        explanation=spec.explanation,
        kind=spec.kind,
        tools=spec.tools,
        tools_used=list(spec.tools_used),
        system_prompt=base_system_prompt() if spec.llm_driven else None,
        system_guardrails=(
            [SystemGuardrailView.model_validate(item) for item in system_guardrails_view()]
            if spec.llm_driven
            else []
        ),
        llm_driven=spec.llm_driven,
        configurable=configurable,
        config_source=spec.config_source,
        effective=effective,
        profiles=named,
    )


async def _agent_response(
    spec: AgentSpec,
    session: AsyncSession,
    settings: Settings,
) -> AgentConfigView:
    _, resolved, _, capabilities = await _load(session, settings)
    rows = await AgentProfileRepository(session).list_for(spec.key)
    return _agent_view(spec, rows, settings, resolved, capabilities)


def _validated_persona(persona: str | None, settings: Settings) -> str | None:
    cleaned = (persona or "").strip() or None
    if cleaned and len(cleaned) > settings.AGENT_PERSONA_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"persona is {len(cleaned)} chars, over the "
                f"{settings.AGENT_PERSONA_MAX_CHARS} cap. || La persona excede el tope."
            ),
        )
    return cleaned


def _validated_guardrails(guardrails: str | None, settings: Settings) -> str | None:
    """Same cap as persona: operator extras share one budget.

    || El mismo tope que persona: los extras de operador comparten presupuesto.
    """
    cleaned = (guardrails or "").strip() or None
    if cleaned and len(cleaned) > settings.AGENT_PERSONA_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"guardrails is {len(cleaned)} chars, over the "
                f"{settings.AGENT_PERSONA_MAX_CHARS} cap. || Los guardrails exceden el tope."
            ),
        )
    return cleaned


def _provider_view(provider: ResolvedProvider, model_count: int) -> ProviderView:
    return ProviderView(
        id=provider.id,
        label=provider.label,
        wire=provider.wire,
        wire_label=WIRE_LABELS.get(provider.wire, provider.wire),
        base_url=provider.base_url,
        enabled=provider.enabled,
        available=provider.available,
        api_key_setting=provider.api_key_setting,
        key_source=provider.key_source,
        api_key_hint=provider.api_key_hint,
        model_count=model_count,
        note=provider.note,
    )


def _model_view(row: ProviderModelRow, resolved: dict[str, ResolvedProvider]) -> ModelView:
    provider = resolved.get(row.provider_id)
    return ModelView(
        provider=row.provider_id,
        model=row.model,
        available=bool(provider and provider.available),
        supports_temperature=row.supports_temperature,
        visible=row.visible,
    )


async def _load(session: AsyncSession, settings: Settings):
    """Every row the config surface needs, resolved once.

    || Todas las filas que necesita la superficie de config, resueltas una vez.
    """
    repository = ProviderRepository(session)
    rows = await repository.providers()
    models = await repository.models()
    resolved = {row.id: resolve_provider(row, settings) for row in rows}
    capabilities = {(m.provider_id, m.model): m.supports_temperature for m in models}
    return repository, resolved, models, capabilities


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


async def _validated_pair(
    provider: str | None,
    model: str | None,
    settings: Settings,
    resolved: dict[str, ResolvedProvider],
    models: list[ProviderModelRow],
) -> tuple[str | None, str | None]:
    """Validate the (provider, model) pair, or explain why it cannot be used.

    The pair is validated together and stored together. A model with no
    provider is read against the service default provider, so "gpt-4o with the
    Anthropic default" is refused rather than stored as a combination nobody
    can run. A hidden model is refused too: hiding it is a decision, and
    honouring it only in the dropdown would make the API the way around it.

    || Valida el par (proveedor, modelo) junto, y junto se guarda. Un modelo
    oculto también se rechaza: ocultarlo es una decisión, y respetarla solo en
    el desplegable haría de la API la forma de saltearla.
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
    entry = next(
        (m for m in models if m.provider_id == effective_provider and m.model == model), None
    )
    if entry is None or not entry.visible:
        offered = ", ".join(f"{m.provider_id}:{m.model}" for m in models if m.visible)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{effective_provider}:{model} is not an offered model ({offered}). "
                "|| Ese par proveedor:modelo no está entre los ofrecidos."
            ),
        )

    target = resolved.get(effective_provider)
    if target is None or not target.available:
        setting = (target.api_key_setting if target else None) or "its API key"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{effective_provider} has no usable credential ({setting} in the environment, "
                "or a stored one), so this model would fail at answer time. Rejected here "
                f"instead. || {effective_provider} no tiene credencial usable ({setting} en el "
                "entorno, o una guardada), así que este modelo fallaría al responder."
            ),
        )

    return effective_provider, model


@router.get("", response_model=ServiceConfigResponse)
async def read_config(
    session: AsyncSession = Depends(get_async_session),  # noqa: B008 — FastAPI's required DI idiom.
) -> ServiceConfigResponse:
    """Providers, models and the agent catalog, with what is in force.

    || Proveedores, modelos y el catálogo de agentes, con lo que está vigente.
    """
    settings = get_settings()
    _, resolved, models, capabilities = await _load(session, settings)
    profiles = await AgentProfileRepository(session).all()

    per_provider: dict[str, int] = {}
    for row in models:
        per_provider[row.provider_id] = per_provider.get(row.provider_id, 0) + 1

    served_flow = graph_flow()
    return ServiceConfigResponse(
        providers=[
            _provider_view(provider, per_provider.get(provider.id, 0))
            for provider in resolved.values()
        ],
        models=[_model_view(row, resolved) for row in models],
        persona_max_chars=settings.AGENT_PERSONA_MAX_CHARS,
        guardrails_max_chars=settings.AGENT_PERSONA_MAX_CHARS,
        persona_template=PERSONA_TEMPLATE,
        guardrails_template=GUARDRAILS_TEMPLATE,
        tools=[ToolCatalogView.model_validate(item) for item in tool_catalog()],
        agents=[
            _agent_view(spec, profiles.get(spec.key, []), settings, resolved, capabilities)
            for spec in AGENT_SPECS
        ],
        credential_storage_enabled=secrets_enabled(),
        wires=dict(WIRE_LABELS),
        flow=GraphFlowView.model_validate(served_flow),
    )


@router.put("/agents/{agent_key}", response_model=AgentConfigView)
async def update_agent_profile(
    agent_key: str,
    body: AgentProfileUpdate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Update the default named profile (creates ``Default`` if none exists).

    Alias kept so the previous console form and its tests keep working. New
    callers should use ``POST/PUT /config/agents/{key}/profiles``.

    || Actualiza el perfil default nombrado (crea ``Default`` si no hay). Alias
    para que el formulario anterior y sus tests sigan funcionando.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)
    _, resolved, models, _ = await _load(session, settings)

    persona = _validated_persona(body.persona, settings)
    guardrails = _validated_guardrails(body.guardrails, settings)
    provider, model = await _validated_pair(body.provider, body.model, settings, resolved, models)

    profile = await AgentProfileRepository(session).upsert(
        agent_key,
        persona=persona,
        guardrails=guardrails,
        provider=provider,
        model=model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    log.info(
        "agent_profile_updated",
        agent=agent_key,
        profile_id=profile.id,
        provider=provider,
        model=model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        persona_chars=len(persona or ""),
        guardrails_chars=len(guardrails or ""),
    )
    return await _agent_response(spec, session, settings)


@router.delete("/agents/{agent_key}", response_model=AgentConfigView)
async def delete_agent_profile(
    agent_key: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Drop every named profile of ``agent_key`` so it runs on Settings again.

    || Borra todos los perfiles nombrados de ``agent_key`` para volver a Settings.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)
    deleted = await AgentProfileRepository(session).delete(agent_key)
    log.info("agent_profile_deleted", agent=agent_key, existed=deleted)
    return await _agent_response(spec, session, settings)


async def _write_named_profile_knobs(
    body: NamedProfileWrite,
    settings: Settings,
    session: AsyncSession,
) -> tuple[str, str | None, str | None, str | None, str | None, float | None, int | None]:
    _, resolved, models, _ = await _load(session, settings)
    persona = _validated_persona(body.persona, settings)
    guardrails = _validated_guardrails(body.guardrails, settings)
    provider, model = await _validated_pair(body.provider, body.model, settings, resolved, models)
    return body.name, persona, guardrails, provider, model, body.temperature, body.max_tokens


@router.post("/agents/{agent_key}/profiles", response_model=AgentConfigView)
async def create_named_profile(
    agent_key: str,
    body: NamedProfileWrite,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Create a named profile for a configurable agent.

    || Crea un perfil nombrado de un agente configurable.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)
    name, persona, guardrails, provider, model, temperature, max_tokens = (
        await _write_named_profile_knobs(body, settings, session)
    )
    try:
        created = await AgentProfileRepository(session).create(
            agent_key,
            name=name,
            is_default=body.is_default,
            persona=persona,
            guardrails=guardrails,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except ProfileValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail
        ) from exc
    log.info("named_profile_created", agent=agent_key, profile_id=created.id, name=created.name)
    return await _agent_response(spec, session, settings)


@router.put("/agents/{agent_key}/profiles/{profile_id}", response_model=AgentConfigView)
async def update_named_profile(
    agent_key: str,
    profile_id: str,
    body: NamedProfileWrite,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Replace a named profile. 404 if it is missing or belongs to another agent.

    || Reemplaza un perfil nombrado. 404 si falta o es de otro agente.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)
    repo = AgentProfileRepository(session)
    existing = await repo.get_by_id(profile_id)
    if existing is None or existing.agent_key != agent_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No profile {profile_id!r} for {agent_key!r}. || No existe ese perfil.",
        )
    name, persona, guardrails, provider, model, temperature, max_tokens = (
        await _write_named_profile_knobs(body, settings, session)
    )
    try:
        await repo.update(
            profile_id,
            name=name,
            is_default=body.is_default,
            persona=persona,
            guardrails=guardrails,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except ProfileValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail
        ) from exc
    log.info("named_profile_updated", agent=agent_key, profile_id=profile_id, name=name)
    return await _agent_response(spec, session, settings)


@router.delete("/agents/{agent_key}/profiles/{profile_id}", response_model=AgentConfigView)
async def delete_named_profile(
    agent_key: str,
    profile_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> AgentConfigView:
    """Delete one named profile. Promotes a sibling if it was the default.

    || Borra un perfil nombrado. Promociona a un hermano si era el default.
    """
    settings = get_settings()
    spec = _require_configurable(agent_key)
    repo = AgentProfileRepository(session)
    existing = await repo.get_by_id(profile_id)
    if existing is None or existing.agent_key != agent_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No profile {profile_id!r} for {agent_key!r}. || No existe ese perfil.",
        )
    await repo.delete_one(profile_id)
    log.info("named_profile_deleted", agent=agent_key, profile_id=profile_id)
    return await _agent_response(spec, session, settings)


# --- Proveedores || Providers -------------------------------------------------


class ProviderUpdate(BaseModel):
    """Body of ``PUT /config/providers/{id}`` — everything EXCEPT the credential.

    The credential has its own endpoint on purpose: mixing it in here would
    mean a form that edits a label also carries a secret, and a partial update
    would have to guess whether an absent key means "leave it" or "clear it".

    || Body de ``PUT /config/providers/{id}`` — todo MENOS la credencial. La
    credencial tiene su propio endpoint a propósito: mezclarla acá haría que un
    formulario que edita un label lleve un secreto, y un update parcial tendría
    que adivinar si una clave ausente significa "dejala" o "borrala".
    """

    label: str | None = Field(default=None, min_length=1, max_length=64)
    base_url: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    note: str | None = None


class ProviderKeyUpdate(BaseModel):
    """Body of ``PUT /config/providers/{id}/key``. Write-only.

    || Body de ``PUT /config/providers/{id}/key``. Solo escritura.
    """

    api_key: str = Field(
        min_length=8,
        description="Stored encrypted; never returned by any endpoint. "
        "|| Se guarda cifrada; ningún endpoint la devuelve.",
    )


class ModelUpdate(BaseModel):
    """Body of ``PUT /config/providers/{id}/models/{model}``."""

    supports_temperature: bool | None = None
    visible: bool | None = None


class ModelCreate(BaseModel):
    """Body of ``POST /config/providers/{id}/models``."""

    model: str = Field(min_length=1, max_length=96)
    supports_temperature: bool | None = Field(
        default=None,
        description="Defaults to what the code knows about this model id. "
        "|| Por default, lo que el código sabe de este id de modelo.",
    )


async def _require_provider(
    provider_id: str, session: AsyncSession, settings: Settings
) -> ResolvedProvider:
    row = await ProviderRepository(session).provider(provider_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No provider {provider_id!r}. || No existe el proveedor {provider_id!r}.",
        )
    return resolve_provider(row, settings)


async def _provider_response(
    provider_id: str, session: AsyncSession, settings: Settings
) -> ProviderView:
    """Re-read the row and shape it, so the response is what is now stored.

    || Vuelve a leer la fila y le da forma, así la respuesta es lo que quedó.
    """
    repository = ProviderRepository(session)
    row = await repository.provider(provider_id)
    assert row is not None
    models = await repository.models()
    count = sum(1 for model in models if model.provider_id == provider_id)
    return _provider_view(resolve_provider(row, settings), count)


@router.put("/providers/{provider_id}", response_model=ProviderView)
async def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ProviderView:
    """Edit a provider's label, base URL, note or enabled flag.

    || Edita el label, la base URL, la nota o el flag de habilitado.
    """
    settings = get_settings()
    await _require_provider(provider_id, session, settings)
    await ProviderRepository(session).update_provider(
        provider_id,
        label=body.label,
        base_url=body.base_url,
        enabled=body.enabled,
        note=body.note,
    )
    log.info("provider_updated", provider=provider_id, enabled=body.enabled)
    return await _provider_response(provider_id, session, settings)


@router.put("/providers/{provider_id}/key", response_model=ProviderView)
async def set_provider_key(
    provider_id: str,
    body: ProviderKeyUpdate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ProviderView:
    """Store a provider credential, encrypted.

    Refuses when no master key is configured: storing it in the clear is not
    an option this endpoint offers, because that is how a database dump ends
    up carrying live credentials.

    || Guarda una credencial de proveedor, cifrada. Se rechaza si no hay master
    key configurada: guardarla en claro no es una opción que este endpoint
    ofrezca, porque así es como un dump termina con credenciales vivas.
    """
    settings = get_settings()
    await _require_provider(provider_id, session, settings)

    if not secrets_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "SECRETS_KEY is not configured, so credentials cannot be stored. Set it in "
                "the environment (generate one with scripts/generate_secrets_key.py), or use "
                "the provider's own environment variable instead. "
                "|| SECRETS_KEY no está configurada, así que no se pueden guardar "
                "credenciales. Definila en el entorno, o usá la variable de entorno del "
                "proveedor."
            ),
        )

    row = await ProviderRepository(session).set_api_key(provider_id, body.api_key.strip())
    assert row is not None
    # The hint, never the key, and never its length either.
    # || El hint, nunca la clave, y tampoco su longitud.
    log.info("provider_key_stored", provider=provider_id, hint=row.api_key_hint)
    return await _provider_response(provider_id, session, settings)


@router.delete("/providers/{provider_id}/key", response_model=ProviderView)
async def clear_provider_key(
    provider_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ProviderView:
    """Forget a stored credential. The environment variable, if any, remains.

    || Olvida una credencial guardada. La variable de entorno, si hay, queda.
    """
    settings = get_settings()
    await _require_provider(provider_id, session, settings)
    await ProviderRepository(session).clear_api_key(provider_id)
    log.info("provider_key_cleared", provider=provider_id)
    return await _provider_response(provider_id, session, settings)


# --- Modelos || Models --------------------------------------------------------


@router.post("/providers/{provider_id}/models", response_model=ModelView)
async def add_model(
    provider_id: str,
    body: ModelCreate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ModelView:
    """Offer one more model of this provider.

    || Ofrece un modelo más de este proveedor.
    """
    settings = get_settings()
    await _require_provider(provider_id, session, settings)
    capability = (
        supports_temperature_default(body.model)
        if body.supports_temperature is None
        else body.supports_temperature
    )
    row = await ProviderRepository(session).upsert_model(
        provider_id, body.model.strip(), supports_temperature=capability
    )
    log.info("provider_model_added", provider=provider_id, model=row.model)
    _, resolved, _, _ = await _load(session, settings)
    return _model_view(row, resolved)


@router.put("/providers/{provider_id}/models/{model}", response_model=ModelView)
async def update_model(
    provider_id: str,
    model: str,
    body: ModelUpdate,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ModelView:
    """Change a model's visibility or its sampling capability.

    || Cambia la visibilidad de un modelo o su capacidad de sampling.
    """
    settings = get_settings()
    row = await ProviderRepository(session).update_model(
        provider_id,
        model,
        supports_temperature=body.supports_temperature,
        visible=body.visible,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No model {provider_id}:{model}. || No existe el modelo.",
        )
    log.info(
        "provider_model_updated",
        provider=provider_id,
        model=model,
        visible=row.visible,
        supports_temperature=row.supports_temperature,
    )
    _, resolved, _, _ = await _load(session, settings)
    return _model_view(row, resolved)


@router.delete("/providers/{provider_id}/models/{model}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    provider_id: str,
    model: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> None:
    """Remove a model from the offering entirely.

    || Saca un modelo de la oferta por completo.
    """
    deleted = await ProviderRepository(session).delete_model(provider_id, model)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No model {provider_id}:{model}. || No existe el modelo.",
        )
    log.info("provider_model_deleted", provider=provider_id, model=model)


class ModelRefreshResponse(BaseModel):
    """Result of asking a provider what it serves. || Resultado de preguntarle al proveedor."""

    provider: str
    reported: int = Field(description="How many ids the provider listed. || Cuántos ids listó.")
    added: list[str] = Field(
        default_factory=list, description="Newly stored, hidden by default. || Nuevos, ocultos."
    )
    already_known: int = 0


@router.post("/providers/{provider_id}/models/refresh", response_model=ModelRefreshResponse)
async def refresh_models(
    provider_id: str,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ModelRefreshResponse:
    """Ask the provider which models it serves and store the new ones.

    New ids arrive **hidden**: a provider's listing includes things that are
    not chat models at all (embeddings, audio, old snapshots), and deciding
    which to offer is curation, not something the provider answers for us.
    Existing rows are left untouched, so a model somebody hid stays hidden.

    || Le pregunta al proveedor qué modelos sirve y guarda los nuevos. Los ids
    nuevos llegan OCULTOS: el listado incluye cosas que no son modelos de chat
    (embeddings, audio, snapshots viejos), y decidir cuáles ofrecer es
    curaduría. Las filas existentes no se tocan, así que un modelo que alguien
    ocultó sigue oculto.
    """
    settings = get_settings()
    provider = await _require_provider(provider_id, session, settings)
    if not provider.available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{provider_id} has no usable credential, so its catalog cannot be read. "
                f"|| {provider_id} no tiene credencial usable, así que no se puede leer su "
                "catálogo."
            ),
        )

    try:
        reported = list_provider_models(provider)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    repository = ProviderRepository(session)
    known = {row.model for row in await repository.models() if row.provider_id == provider_id}
    added = [model_id for model_id in reported if model_id not in known]
    await repository.upsert_models(
        provider_id,
        [(model_id, supports_temperature_default(model_id), False) for model_id in added],
    )

    log.info(
        "provider_models_refreshed",
        provider=provider_id,
        reported=len(reported),
        added=len(added),
    )
    return ModelRefreshResponse(
        provider=provider_id,
        reported=len(reported),
        added=added,
        already_known=len(reported) - len(added),
    )
