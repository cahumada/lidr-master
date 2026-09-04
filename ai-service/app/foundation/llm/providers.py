"""Which providers exist, which models they serve, and what each model accepts.

One place decides three things, so nothing downstream has to guess:

1. **Which client to build.** Moonshot (Kimi) speaks OpenAI's wire format, so
   it is the OpenAI client pointed at another ``base_url`` — two adapters for
   three providers. Anthropic gets its own.
2. **Whether a provider is usable at all.** A provider with no API key
   configured is reported unavailable, so choosing it fails in the console
   with a clear message instead of at answer time with a 500.
3. **Whether a model accepts ``temperature``.** Current Claude models
   (``claude-opus-5``, ``claude-sonnet-5``) **reject sampling parameters with
   a 400** — `temperature` was removed on that generation; `claude-haiku-4-5`
   still takes it. Sending it anyway would turn "pick Sonnet" into a broken
   endpoint, so the catalog carries the capability and the adapter omits what
   the model will not take.

What this deliberately does NOT touch: **embeddings**. The 57.101 stored
vectors are in ``text-embedding-3-small`` space, and an embedding from another
provider is not comparable to them — switching that is a corpus rebuild, not a
setting. Multi-provider here means the *answer* model. The reranker also stays
on OpenAI: it is not agent-configurable, so it has no profile to read.

|| Qué proveedores existen, qué modelos sirven, y qué acepta cada modelo. Un
solo lugar decide tres cosas: qué cliente armar (Moonshot habla el formato de
OpenAI, así que son dos adaptadores para tres proveedores), si un proveedor es
usable (sin clave se reporta no disponible, y elegirlo falla en la consola con
un mensaje claro en vez de a la hora de responder con un 500), y si un modelo
acepta ``temperature`` — los modelos Claude actuales la RECHAZAN con un 400.

Lo que a propósito NO toca: los **embeddings**. Las 57.101 filas están en el
espacio de ``text-embedding-3-small`` y un embedding de otro proveedor no es
comparable con ellas — cambiarlo es reconstruir el corpus, no un setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import structlog

from app.config import Settings, get_settings
from app.foundation.llm.wrapper import LLM, AnthropicChatLLM, OpenAICompatibleChatLLM

log = structlog.get_logger()


class LLMProviderError(RuntimeError):
    """The provider cannot be used as configured.

    || El proveedor no se puede usar como está configurado.
    """


ProviderId = Literal["openai", "anthropic", "moonshot"]

OPENAI = "openai"
ANTHROPIC = "anthropic"
MOONSHOT = "moonshot"

# Wire formats, not brands: `openai_compatible` is whatever speaks
# `/chat/completions`, which today is OpenAI itself and Moonshot.
# || Formatos de wire, no marcas.
_OPENAI_COMPATIBLE = "openai_compatible"
_ANTHROPIC_MESSAGES = "anthropic_messages"


@dataclass(frozen=True)
class ProviderSpec:
    """One provider: how to reach it and how to talk to it.

    || Un proveedor: cómo llegarle y cómo hablarle.
    """

    id: str
    label: str
    wire: str
    api_key_setting: str
    base_url_setting: str | None = None
    docs_note: str = ""


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id=OPENAI,
        label="OpenAI",
        wire=_OPENAI_COMPATIBLE,
        api_key_setting="OPENAI_API_KEY",
        docs_note="También es el proveedor de los embeddings del corpus, que no son configurables.",
    ),
    ProviderSpec(
        id=ANTHROPIC,
        label="Anthropic",
        wire=_ANTHROPIC_MESSAGES,
        api_key_setting="ANTHROPIC_API_KEY",
        docs_note="Messages API: `system` va como parámetro y no como mensaje.",
    ),
    ProviderSpec(
        id=MOONSHOT,
        label="Moonshot (Kimi)",
        wire=_OPENAI_COMPATIBLE,
        api_key_setting="MOONSHOT_API_KEY",
        base_url_setting="MOONSHOT_BASE_URL",
        docs_note="API compatible con OpenAI: mismo adaptador, otro base_url.",
    ),
)

_PROVIDERS_BY_ID = {spec.id: spec for spec in PROVIDER_SPECS}

# Models that do NOT accept `temperature`. Anthropic removed the sampling
# parameters on this generation: sending one returns a 400. Kept as an
# explicit deny-list rather than "anthropic rejects temperature", because
# `claude-haiku-4-5` still accepts it — the capability belongs to the model,
# not to the provider.
# || Modelos que NO aceptan `temperature`. Anthropic removió los parámetros de
# sampling en esta generación: mandar uno devuelve 400. Es una lista explícita
# y no "anthropic no acepta temperature", porque `claude-haiku-4-5` sí la
# acepta — la capacidad es del modelo, no del proveedor.
_MODELS_WITHOUT_TEMPERATURE = frozenset(
    {
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-fable-5",
        "claude-fable-5-1",
    }
)


@dataclass(frozen=True)
class CatalogEntry:
    """One selectable model, with the provider that serves it.

    || Un modelo elegible, con el proveedor que lo sirve.
    """

    provider: str
    model: str

    @property
    def supports_temperature(self) -> bool:
        """Whether this model accepts a ``temperature``.

        || Si este modelo acepta ``temperature``.
        """
        return self.model not in _MODELS_WITHOUT_TEMPERATURE


def provider_spec(provider: str) -> ProviderSpec | None:
    """The spec for ``provider``, or ``None``. || El spec del proveedor, o ``None``."""
    return _PROVIDERS_BY_ID.get(provider)


def api_key_for(provider: str, settings: Settings) -> str:
    """The configured key for ``provider``, or an empty string.

    || La clave configurada del proveedor, o cadena vacía.
    """
    spec = provider_spec(provider)
    if spec is None:
        return ""
    return str(getattr(settings, spec.api_key_setting, "") or "")


def is_available(provider: str, settings: Settings) -> bool:
    """Whether ``provider`` has a key configured. || Si el proveedor tiene clave."""
    return bool(api_key_for(provider, settings))


def parse_catalog(settings: Settings) -> list[CatalogEntry]:
    """Parse ``ANSWER_MODEL_CATALOG`` entries of the form ``provider:model``.

    An entry naming an unknown provider is dropped with a warning rather than
    crashing the service: a typo in an env var should not take the whole
    thing down, and the console showing one model fewer is a visible symptom.

    || Parsea las entradas ``proveedor:modelo`` de ``ANSWER_MODEL_CATALOG``.
    Una entrada con un proveedor desconocido se descarta con un warning en vez
    de tirar el servicio: un typo en una env var no debería voltearlo todo, y
    que la consola muestre un modelo menos es un síntoma visible.
    """
    entries: list[CatalogEntry] = []
    for raw in settings.ANSWER_MODEL_CATALOG:
        provider, separator, model = str(raw).partition(":")
        if not separator or not model:
            log.warning("model_catalog_entry_malformed", entry=raw)
            continue
        if provider not in _PROVIDERS_BY_ID:
            log.warning("model_catalog_unknown_provider", entry=raw, provider=provider)
            continue
        entries.append(CatalogEntry(provider=provider, model=model))
    return entries


def catalog_entry(provider: str, model: str, settings: Settings) -> CatalogEntry | None:
    """The catalog entry for this pair, or ``None`` if it is not offered.

    || La entrada del catálogo para este par, o ``None`` si no se ofrece.
    """
    for entry in parse_catalog(settings):
        if entry.provider == provider and entry.model == model:
            return entry
    return None


def supports_temperature(model: str) -> bool:
    """Whether ``model`` accepts a ``temperature`` parameter.

    || Si ``model`` acepta un parámetro ``temperature``.
    """
    return model not in _MODELS_WITHOUT_TEMPERATURE


@lru_cache
def _client_for(provider: str) -> Any:
    """The provider's SDK client, built once per provider.

    || El cliente del SDK del proveedor, armado una vez por proveedor.
    """
    settings = get_settings()
    spec = provider_spec(provider)
    if spec is None:
        raise LLMProviderError(f"unknown provider {provider!r} || proveedor desconocido")

    key = api_key_for(provider, settings)
    if not key:
        raise LLMProviderError(
            f"{spec.label} has no API key configured ({spec.api_key_setting}). "
            f"|| {spec.label} no tiene clave configurada ({spec.api_key_setting})."
        )

    if spec.wire == _ANTHROPIC_MESSAGES:
        import anthropic

        return anthropic.Anthropic(api_key=key)

    from openai import OpenAI

    base_url = None
    if spec.base_url_setting:
        base_url = str(getattr(settings, spec.base_url_setting, "") or "") or None
    return OpenAI(api_key=key, base_url=base_url)


def build_llm(
    provider: str,
    model: str,
    *,
    max_tokens: int,
    temperature: float | None,
) -> LLM:
    """An ``LLM`` for one explicit provider and model.

    ``temperature`` is dropped when the model does not accept it, rather than
    sent and rejected with a 400. The drop is logged: a knob that silently
    stops applying is worse than one that says so.

    || Un ``LLM`` para un proveedor y un modelo explícitos. La ``temperature``
    se descarta cuando el modelo no la acepta, en vez de mandarla y comerse un
    400. El descarte se loguea: un knob que deja de aplicar en silencio es
    peor que uno que lo dice.
    """
    spec = provider_spec(provider)
    if spec is None:
        raise LLMProviderError(f"unknown provider {provider!r} || proveedor desconocido")

    effective_temperature = temperature
    if temperature is not None and not supports_temperature(model):
        log.info("llm_temperature_dropped", provider=provider, model=model)
        effective_temperature = None

    client = _client_for(provider)
    if spec.wire == _ANTHROPIC_MESSAGES:
        return AnthropicChatLLM(
            client, model=model, max_tokens=max_tokens, temperature=effective_temperature
        )
    return OpenAICompatibleChatLLM(
        client, model=model, max_tokens=max_tokens, temperature=effective_temperature
    )
