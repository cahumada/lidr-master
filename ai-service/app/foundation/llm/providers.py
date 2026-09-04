"""Which wire formats exist, and how to build a client for one.

This module used to own the provider list. It no longer does: providers and
their models live in the database (`app/domain/providers_store.py`), so adding
one is a row and not a deploy. What stays here is the part that genuinely IS
code:

1. **The wires.** Two adapters cover every provider we can talk to:
   ``openai_compatible`` (OpenAI itself, Moonshot/Kimi, and anything else
   serving `/chat/completions` — Groq, DeepSeek, a local vLLM) and
   ``anthropic_messages``. A provider row claiming a wire nobody implemented
   would be a lie the console would display, so the wires are validated
   against this list.
2. **The seed.** `SEED_PROVIDERS` and the capability defaults are what a fresh
   install starts from, so the service behaves as it did before there were
   tables to read.
3. **The client cache.** SDK clients are cached by (wire, base_url, key) so a
   request does not build one per call.

What this deliberately does NOT touch: **embeddings**. The stored vectors
belong to one embedding model's space, so switching that provider is a corpus
rebuild, not a setting. Multi-provider here means the *answer* model.

|| Este módulo ya no es dueño de la lista de proveedores: viven en la base, así
que agregar uno es una fila y no un deploy. Acá queda lo que sí es código: los
dos wires (`openai_compatible` cubre OpenAI, Moonshot y cualquier otro que
sirva `/chat/completions`; `anthropic_messages` el suyo), la semilla del primer
arranque, y el cache de clientes del SDK.

Lo que a propósito NO toca: los embeddings. Los vectores guardados pertenecen
al espacio de un modelo; cambiar ese proveedor es reconstruir el corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import structlog

from app.foundation.llm.wrapper import LLM, AnthropicChatLLM, OpenAICompatibleChatLLM

log = structlog.get_logger()


class LLMProviderError(RuntimeError):
    """The provider cannot be used as configured.

    || El proveedor no se puede usar como está configurado.
    """


OPENAI = "openai"
ANTHROPIC = "anthropic"
MOONSHOT = "moonshot"

# Wire formats, not brands. Adding a provider that speaks one of these is a
# database row; adding a NEW wire is this file plus an adapter.
# || Formatos de wire, no marcas. Agregar un proveedor que habla uno de estos
# es una fila; agregar un wire NUEVO es este archivo más un adaptador.
OPENAI_COMPATIBLE = "openai_compatible"
ANTHROPIC_MESSAGES = "anthropic_messages"

WIRES: frozenset[str] = frozenset({OPENAI_COMPATIBLE, ANTHROPIC_MESSAGES})

WIRE_LABELS: dict[str, str] = {
    OPENAI_COMPATIBLE: "OpenAI-compatible (/chat/completions)",
    ANTHROPIC_MESSAGES: "Anthropic Messages API",
}


@dataclass(frozen=True)
class SeedProvider:
    """A provider the service knows how to reach out of the box.

    || Un proveedor que el servicio sabe alcanzar de fábrica.
    """

    id: str
    label: str
    wire: str
    api_key_setting: str
    base_url: str | None = None
    note: str = ""


SEED_PROVIDERS: tuple[SeedProvider, ...] = (
    SeedProvider(
        id=OPENAI,
        label="OpenAI",
        wire=OPENAI_COMPATIBLE,
        api_key_setting="OPENAI_API_KEY",
        note=(
            "También sirve a los embeddings del corpus y al reranker, que no son "
            "multi-proveedor: los vectores guardados viven en el espacio de "
            "text-embedding-3-small."
        ),
    ),
    SeedProvider(
        id=ANTHROPIC,
        label="Anthropic",
        wire=ANTHROPIC_MESSAGES,
        api_key_setting="ANTHROPIC_API_KEY",
        note="Messages API: `system` va como parámetro y no como mensaje.",
    ),
    SeedProvider(
        id=MOONSHOT,
        label="Moonshot (Kimi)",
        wire=OPENAI_COMPATIBLE,
        api_key_setting="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.ai/v1",
        note="API compatible con OpenAI: mismo adaptador, otro base_url.",
    ),
)

# Models known NOT to accept `temperature`. This is only the SEED for a
# model row's capability — once the row exists, the database is the authority,
# because a provider can ship a model whose behaviour this list has never
# seen and waiting for a deploy to record that is how a 400 stays broken.
#
# Anthropic removed the sampling parameters on this generation: sending
# `temperature` returns a 400. `claude-haiku-4-5` still accepts it, which is
# why the capability belongs to the MODEL and not to the provider.
# || Modelos que se sabe que NO aceptan `temperature`. Es solo la SEMILLA de la
# capacidad de la fila: una vez que la fila existe, la base es la autoridad.
MODELS_WITHOUT_TEMPERATURE = frozenset(
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

def seed_provider(provider_id: str) -> SeedProvider | None:
    """The built-in seed for ``provider_id``, or ``None``.

    || La semilla incorporada para ``provider_id``, o ``None``.
    """
    for spec in SEED_PROVIDERS:
        if spec.id == provider_id:
            return spec
    return None


def supports_temperature_default(model: str) -> bool:
    """The seed capability for a model the database has not recorded yet.

    || La capacidad semilla de un modelo que la base todavía no registró.
    """
    return model not in MODELS_WITHOUT_TEMPERATURE


def assert_known_wire(wire: str) -> None:
    """Reject a wire no adapter implements. || Rechaza un wire sin adaptador."""
    if wire not in WIRES:
        raise LLMProviderError(
            f"unknown wire {wire!r}; this service implements {sorted(WIRES)} "
            f"|| wire desconocido {wire!r}"
        )


@lru_cache
def _client(wire: str, base_url: str | None, api_key: str) -> Any:
    """The SDK client for one (wire, base_url, key), built once.

    Cached so a request does not construct an SDK client per call. The key is
    part of the cache key by necessity — it is already in memory as the
    client's own attribute — and never leaves this process.

    || El cliente del SDK para un (wire, base_url, clave), armado una vez. La
    clave es parte de la clave de cache por necesidad: ya está en memoria como
    atributo del propio cliente, y nunca sale de este proceso.
    """
    assert_known_wire(wire)

    if wire == ANTHROPIC_MESSAGES:
        import anthropic

        return anthropic.Anthropic(api_key=api_key, base_url=base_url or None)

    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url or None)


def build_llm_for(
    provider: Any,
    model: str,
    *,
    max_tokens: int,
    temperature: float | None,
    supports_temperature: bool = True,
) -> LLM:
    """An ``LLM`` for a resolved provider and one of its models.

    ``provider`` is a ``ResolvedProvider`` (see
    ``app/domain/providers_store.py``) — taken as ``Any`` so this foundation
    module does not import the domain layer that stores it.

    ``temperature`` is dropped when the model does not accept one, rather than
    sent and answered with a 400. The drop is logged: a knob that silently
    stops applying is worse than one that says so.

    || Un ``LLM`` para un proveedor ya resuelto y uno de sus modelos. La
    ``temperature`` se descarta cuando el modelo no la acepta, en vez de
    mandarla y comerse un 400. El descarte se loguea.
    """
    if not provider.enabled:
        raise LLMProviderError(
            f"provider {provider.id!r} is disabled || el proveedor está deshabilitado"
        )
    if not provider.api_key:
        setting = provider.api_key_setting or "its API key"
        raise LLMProviderError(
            f"provider {provider.id!r} has no credential: set {setting} in the environment "
            f"or store one from the console || el proveedor no tiene credencial"
        )

    effective_temperature = temperature
    if temperature is not None and not supports_temperature:
        log.info("llm_temperature_dropped", provider=provider.id, model=model)
        effective_temperature = None

    client = _client(provider.wire, provider.base_url, provider.api_key)
    if provider.wire == ANTHROPIC_MESSAGES:
        return AnthropicChatLLM(
            client, model=model, max_tokens=max_tokens, temperature=effective_temperature
        )
    return OpenAICompatibleChatLLM(
        client, model=model, max_tokens=max_tokens, temperature=effective_temperature
    )


def list_provider_models(provider: Any) -> list[str]:
    """Ask the provider which models it serves.

    This is the "dynamic catalog" path: both wires expose a models listing, so
    one code path covers all of them. Returns ids as the provider reports
    them; filtering and curation happen where the rows are written, because
    what counts as a *chat* model is a judgement the provider does not make
    for us (OpenAI's list includes embeddings, audio and old snapshots).

    || Le pregunta al proveedor qué modelos sirve. Los dos wires exponen un
    listado, así que un solo camino los cubre. Devuelve los ids como los
    reporta el proveedor; el filtrado y la curaduría van donde se escriben las
    filas, porque qué es un modelo de CHAT es un juicio que el proveedor no
    hace por nosotros.
    """
    client = _client(provider.wire, provider.base_url, provider.api_key)
    try:
        page = client.models.list()
    except Exception as exc:
        raise LLMProviderError(
            f"could not list models for {provider.id!r}: {type(exc).__name__} "
            f"|| no se pudieron listar los modelos de {provider.id!r}"
        ) from exc

    ids: list[str] = []
    for item in getattr(page, "data", None) or page:
        model_id = getattr(item, "id", None)
        if model_id:
            ids.append(str(model_id))
    return sorted(set(ids))
