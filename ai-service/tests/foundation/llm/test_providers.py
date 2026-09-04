"""The provider registry: catalog parsing, availability, capabilities.

|| El registro de proveedores: parseo del catálogo, disponibilidad, capacidades.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.foundation.llm import providers
from app.foundation.llm.providers import (
    ANTHROPIC,
    MOONSHOT,
    OPENAI,
    LLMProviderError,
    api_key_for,
    build_llm,
    catalog_entry,
    is_available,
    parse_catalog,
    provider_spec,
    supports_temperature,
)
from app.foundation.llm.wrapper import AnthropicChatLLM, OpenAICompatibleChatLLM


class TestProviderRegistry:
    def test_the_three_providers_are_known(self):
        assert {spec.id for spec in providers.PROVIDER_SPECS} == {OPENAI, ANTHROPIC, MOONSHOT}

    def test_moonshot_reuses_the_openai_wire_format(self):
        # This is why three providers need only two adapters.
        # || Es por esto que tres proveedores necesitan solo dos adaptadores.
        assert provider_spec(MOONSHOT).wire == provider_spec(OPENAI).wire
        assert provider_spec(ANTHROPIC).wire != provider_spec(OPENAI).wire

    def test_moonshot_declares_a_base_url_setting_and_the_others_do_not(self):
        assert provider_spec(MOONSHOT).base_url_setting == "MOONSHOT_BASE_URL"
        assert provider_spec(OPENAI).base_url_setting is None

    def test_an_unknown_provider_has_no_spec(self):
        assert provider_spec("gemini") is None


class TestAvailability:
    def test_a_provider_with_a_key_is_available(self):
        settings = Settings(ANTHROPIC_API_KEY="sk-ant-x")

        assert is_available(ANTHROPIC, settings) is True
        assert api_key_for(ANTHROPIC, settings) == "sk-ant-x"

    def test_a_provider_without_a_key_is_not(self):
        settings = Settings(ANTHROPIC_API_KEY="", MOONSHOT_API_KEY="")

        assert is_available(ANTHROPIC, settings) is False
        assert is_available(MOONSHOT, settings) is False

    def test_an_unknown_provider_is_never_available(self):
        assert is_available("gemini", Settings()) is False


class TestCatalogParsing:
    def test_entries_are_provider_qualified(self):
        settings = Settings(ANSWER_MODEL_CATALOG=["openai:gpt-4o", "anthropic:claude-opus-5"])

        entries = parse_catalog(settings)

        assert [(e.provider, e.model) for e in entries] == [
            ("openai", "gpt-4o"),
            ("anthropic", "claude-opus-5"),
        ]

    def test_a_malformed_entry_is_dropped_not_fatal(self):
        # A typo in an env var should cost one model in the console, not the
        # whole service.
        # || Un typo en una env var debería costar un modelo en la consola, no
        # el servicio entero.
        settings = Settings(ANSWER_MODEL_CATALOG=["gpt-4o", "openai:gpt-4o-mini"])

        entries = parse_catalog(settings)

        assert [e.model for e in entries] == ["gpt-4o-mini"]

    def test_an_unknown_provider_is_dropped(self):
        settings = Settings(ANSWER_MODEL_CATALOG=["gemini:gemini-2", "openai:gpt-4o"])

        assert [e.provider for e in parse_catalog(settings)] == ["openai"]

    def test_catalog_entry_finds_a_pair_and_rejects_a_crossed_one(self):
        settings = Settings(ANSWER_MODEL_CATALOG=["openai:gpt-4o", "anthropic:claude-opus-5"])

        assert catalog_entry("openai", "gpt-4o", settings) is not None
        # The same model name under the wrong provider is not in the catalog.
        # || El mismo nombre de modelo bajo el proveedor equivocado no está.
        assert catalog_entry("anthropic", "gpt-4o", settings) is None


class TestTemperatureCapability:
    def test_current_claude_models_do_not_accept_temperature(self):
        # Anthropic removed the sampling parameters on this generation:
        # sending `temperature` returns a 400.
        # || Anthropic removió los parámetros de sampling en esta generación:
        # mandar `temperature` devuelve 400.
        assert supports_temperature("claude-opus-5") is False
        assert supports_temperature("claude-sonnet-5") is False

    def test_haiku_and_the_openai_models_do(self):
        # The capability belongs to the MODEL, not to the provider — which is
        # why this is not "anthropic rejects temperature".
        # || La capacidad es del MODELO, no del proveedor.
        assert supports_temperature("claude-haiku-4-5") is True
        assert supports_temperature("gpt-4o-mini") is True
        assert supports_temperature("kimi-k2-0905-preview") is True

    def test_the_catalog_entry_exposes_the_capability(self):
        settings = Settings(ANSWER_MODEL_CATALOG=["anthropic:claude-sonnet-5"])
        [entry] = parse_catalog(settings)

        assert entry.supports_temperature is False


class TestBuildLLM:
    @pytest.fixture(autouse=True)
    def fake_clients(self, monkeypatch):
        """Never build a real SDK client. || Nunca armar un cliente real del SDK."""
        monkeypatch.setattr(providers, "_client_for", lambda provider: object())

    def test_openai_gets_the_openai_compatible_adapter(self):
        llm = build_llm(OPENAI, "gpt-4o-mini", max_tokens=256, temperature=0.0)

        assert isinstance(llm, OpenAICompatibleChatLLM)
        assert llm.temperature == 0.0

    def test_moonshot_gets_the_same_adapter_as_openai(self):
        llm = build_llm(MOONSHOT, "kimi-k2-0905-preview", max_tokens=256, temperature=0.3)

        assert isinstance(llm, OpenAICompatibleChatLLM)
        assert llm.model == "kimi-k2-0905-preview"

    def test_anthropic_gets_the_messages_adapter(self):
        llm = build_llm(ANTHROPIC, "claude-haiku-4-5", max_tokens=1024, temperature=0.2)

        assert isinstance(llm, AnthropicChatLLM)
        assert llm.temperature == 0.2

    def test_temperature_is_dropped_for_a_model_that_rejects_it(self):
        # Dropped here rather than sent and answered with a 400: picking
        # Sonnet must not turn the endpoint into a broken one.
        # || Se descarta acá en vez de mandarla y comerse un 400: elegir
        # Sonnet no puede convertir el endpoint en uno roto.
        llm = build_llm(ANTHROPIC, "claude-sonnet-5", max_tokens=1024, temperature=0.7)

        assert llm.temperature is None

    def test_an_unknown_provider_raises(self):
        with pytest.raises(LLMProviderError, match="unknown provider"):
            build_llm("gemini", "gemini-2", max_tokens=256, temperature=0.0)


class TestClientConstruction:
    def test_a_provider_without_a_key_raises_a_clear_error(self, monkeypatch):
        monkeypatch.setattr(
            "app.foundation.llm.providers.get_settings",
            lambda: Settings(ANTHROPIC_API_KEY=""),
        )
        providers._client_for.cache_clear()

        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):
            providers._client_for(ANTHROPIC)

        providers._client_for.cache_clear()
