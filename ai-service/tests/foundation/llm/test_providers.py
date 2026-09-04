"""Wires, the seed registry, and building a client for a resolved provider.

The provider LIST is no longer here — it lives in the database, and its tests
live in `tests/domain/test_providers_store.py`. What is tested here is the part
that stayed code: which wires exist, what the seed says, and that a resolved
provider produces the right adapter with the right sampling.

|| La LISTA de proveedores ya no está acá: vive en la base. Lo que se prueba
acá es lo que quedó siendo código: qué wires existen, qué dice la semilla, y
que un proveedor resuelto produce el adaptador correcto.
"""

from __future__ import annotations

import pytest

from app.domain.providers_store import ResolvedProvider
from app.foundation.llm import providers
from app.foundation.llm.providers import (
    ANTHROPIC,
    ANTHROPIC_MESSAGES,
    MOONSHOT,
    OPENAI,
    OPENAI_COMPATIBLE,
    WIRES,
    LLMProviderError,
    assert_known_wire,
    build_llm_for,
    seed_provider,
    supports_temperature_default,
)
from app.foundation.llm.wrapper import AnthropicChatLLM, OpenAICompatibleChatLLM


def _resolved(
    provider_id: str = OPENAI,
    *,
    wire: str = OPENAI_COMPATIBLE,
    api_key: str | None = "sk-test",
    base_url: str | None = None,
    enabled: bool = True,
) -> ResolvedProvider:
    return ResolvedProvider(
        id=provider_id,
        label=provider_id,
        wire=wire,
        base_url=base_url,
        enabled=enabled,
        note=None,
        api_key_setting="OPENAI_API_KEY",
        api_key=api_key,
        api_key_hint=None,
        key_source="env" if api_key else "none",
    )


class TestWires:
    def test_the_service_implements_exactly_two_wires(self):
        # Two adapters cover every provider we can talk to. A third wire is
        # this module plus an adapter, not a database row.
        # || Dos adaptadores cubren todos los proveedores que podemos hablar.
        assert WIRES == {OPENAI_COMPATIBLE, ANTHROPIC_MESSAGES}

    def test_an_unimplemented_wire_is_rejected(self):
        # A provider row could name anything; only these two have code.
        # || Una fila de proveedor podría nombrar cualquier cosa.
        with pytest.raises(LLMProviderError, match="unknown wire"):
            assert_known_wire("gemini_native")


class TestSeedRegistry:
    def test_the_three_known_providers_are_seeded(self):
        assert {spec.id for spec in providers.SEED_PROVIDERS} == {OPENAI, ANTHROPIC, MOONSHOT}

    def test_moonshot_reuses_the_openai_wire(self):
        # This is why three providers need only two adapters.
        # || Es por esto que tres proveedores necesitan solo dos adaptadores.
        assert seed_provider(MOONSHOT).wire == seed_provider(OPENAI).wire
        assert seed_provider(ANTHROPIC).wire != seed_provider(OPENAI).wire

    def test_moonshot_seeds_a_base_url_and_the_others_do_not(self):
        assert seed_provider(MOONSHOT).base_url
        assert seed_provider(OPENAI).base_url is None

    def test_an_unknown_provider_has_no_seed(self):
        assert seed_provider("gemini") is None


class TestTemperatureCapabilityDefaults:
    def test_current_claude_models_do_not_accept_temperature(self):
        # Anthropic removed the sampling parameters on this generation:
        # sending `temperature` returns a 400.
        # || Anthropic removió los parámetros de sampling: devuelve 400.
        assert supports_temperature_default("claude-opus-5") is False
        assert supports_temperature_default("claude-sonnet-5") is False

    def test_haiku_and_the_openai_models_do(self):
        # The capability belongs to the MODEL, not the provider.
        # || La capacidad es del MODELO, no del proveedor.
        assert supports_temperature_default("claude-haiku-4-5") is True
        assert supports_temperature_default("gpt-4o-mini") is True
        assert supports_temperature_default("kimi-k2-0905-preview") is True

    def test_an_unknown_model_is_assumed_to_accept_one(self):
        # The optimistic default is deliberate: this is only the SEED for a
        # row that a human (or a refresh) can correct, and assuming "no
        # sampling" for every new model would silently drop a knob that works.
        # || El default optimista es deliberado: esto es solo la SEMILLA de una
        # fila que se puede corregir.
        assert supports_temperature_default("some-future-model") is True


class TestBuildLLMFor:
    @pytest.fixture(autouse=True)
    def fake_clients(self, monkeypatch):
        """Never build a real SDK client. || Nunca armar un cliente real."""
        monkeypatch.setattr(providers, "_client", lambda wire, base_url, api_key: object())

    def test_an_openai_compatible_provider_gets_that_adapter(self):
        llm = build_llm_for(_resolved(), "gpt-4o-mini", max_tokens=256, temperature=0.0)

        assert isinstance(llm, OpenAICompatibleChatLLM)
        assert llm.temperature == 0.0

    def test_moonshot_gets_the_same_adapter_as_openai(self):
        provider = _resolved(MOONSHOT, base_url="https://api.moonshot.ai/v1")

        llm = build_llm_for(provider, "kimi-k2-0905-preview", max_tokens=256, temperature=0.3)

        assert isinstance(llm, OpenAICompatibleChatLLM)
        assert llm.model == "kimi-k2-0905-preview"

    def test_an_anthropic_provider_gets_the_messages_adapter(self):
        provider = _resolved(ANTHROPIC, wire=ANTHROPIC_MESSAGES)

        llm = build_llm_for(provider, "claude-haiku-4-5", max_tokens=1024, temperature=0.2)

        assert isinstance(llm, AnthropicChatLLM)
        assert llm.temperature == 0.2

    def test_temperature_is_dropped_when_the_model_rejects_it(self):
        # Dropped here rather than sent and answered with a 400: picking
        # Sonnet must not turn the endpoint into a broken one.
        # || Se descarta acá en vez de mandarla y comerse un 400.
        provider = _resolved(ANTHROPIC, wire=ANTHROPIC_MESSAGES)

        llm = build_llm_for(
            provider,
            "claude-sonnet-5",
            max_tokens=1024,
            temperature=0.7,
            supports_temperature=False,
        )

        assert llm.temperature is None

    def test_a_provider_without_a_credential_raises(self):
        with pytest.raises(LLMProviderError, match="no credential"):
            build_llm_for(
                _resolved(api_key=None), "gpt-4o-mini", max_tokens=256, temperature=0.0
            )

    def test_a_disabled_provider_raises(self):
        # Disabling is an operator decision; honouring it only in the console
        # would make the API the way around it.
        # || Deshabilitar es una decisión de quien opera.
        with pytest.raises(LLMProviderError, match="disabled"):
            build_llm_for(
                _resolved(enabled=False), "gpt-4o-mini", max_tokens=256, temperature=0.0
            )
