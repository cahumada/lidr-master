"""Tests for how an agent profile merges over the service defaults.

|| Tests de cómo un perfil de agente se mezcla sobre los defaults del servicio.
"""

from __future__ import annotations

from app.config import Settings
from app.domain.profiles import AgentProfileRow, resolve_agent_config


def _settings() -> Settings:
    return Settings(
        ANSWER_PROVIDER="openai",
        ANSWER_MODEL="gpt-4o-mini",
        ANSWER_MAX_TOKENS=1024,
        ANSWER_TEMPERATURE=0.0,
    )


class TestResolveAgentConfig:
    def test_no_profile_uses_every_default(self):
        effective = resolve_agent_config(None, _settings())

        assert effective.provider == "openai"
        assert effective.model == "gpt-4o-mini"
        assert effective.max_tokens == 1024
        assert effective.temperature == 0.0
        assert effective.persona is None
        assert effective.sources == {
            "provider": "settings",
            "model": "settings",
            "temperature": "settings",
            "max_tokens": "settings",
            "persona": "unset",
        }

    def test_profile_overrides_win_and_are_reported_as_such(self):
        profile = AgentProfileRow(
            agent_key="answer_synthesizer",
            persona="Hablás como un analista funcional.",
            provider="openai",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=2048,
        )

        effective = resolve_agent_config(profile, _settings())

        assert effective.provider == "openai"
        assert effective.model == "gpt-4o"
        assert effective.temperature == 0.7
        assert effective.max_tokens == 2048
        assert effective.persona == "Hablás como un analista funcional."
        assert set(effective.sources.values()) == {"profile"}

    def test_a_profile_carries_its_provider_with_its_model(self):
        profile = AgentProfileRow(
            agent_key="answer_synthesizer",
            provider="anthropic",
            model="claude-haiku-4-5",
        )

        effective = resolve_agent_config(profile, _settings())

        assert (effective.provider, effective.model) == ("anthropic", "claude-haiku-4-5")
        assert effective.sources["provider"] == "profile"

    def test_a_model_that_rejects_sampling_reports_no_temperature(self):
        # Current Claude models return a 400 for `temperature`. "No
        # temperature" is a real state, so it is None and its source says why
        # — not silently the settings' value, which would be sent and rejected.
        # || Los modelos Claude actuales devuelven 400 por `temperature`. "Sin
        # temperatura" es un estado real: es None y su fuente dice por qué.
        profile = AgentProfileRow(
            agent_key="answer_synthesizer",
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=0.7,
        )

        effective = resolve_agent_config(profile, _settings())

        assert effective.supports_temperature is False
        assert effective.temperature is None
        assert effective.sources["temperature"] == "unsupported"

    def test_a_partial_profile_only_overrides_what_it_sets(self):
        profile = AgentProfileRow(agent_key="answer_synthesizer", persona="Sé breve.")

        effective = resolve_agent_config(profile, _settings())

        assert effective.persona == "Sé breve."
        assert effective.model == "gpt-4o-mini"
        assert effective.sources["persona"] == "profile"
        assert effective.sources["model"] == "settings"

    def test_temperature_zero_from_a_profile_is_an_override_not_an_absence(self):
        # The bug this guards: `temperature or default` treats a deliberate
        # 0.0 as unset and silently restores the default.
        # || El bug que esto cuida: `temperature or default` toma un 0.0
        # deliberado como no seteado y restaura el default en silencio.
        profile = AgentProfileRow(agent_key="answer_synthesizer", temperature=0.0)
        settings = Settings(ANSWER_TEMPERATURE=0.9)

        effective = resolve_agent_config(profile, settings)

        assert effective.temperature == 0.0
        assert effective.sources["temperature"] == "profile"

    def test_a_blank_persona_reads_as_no_persona(self):
        profile = AgentProfileRow(agent_key="answer_synthesizer", persona="")

        effective = resolve_agent_config(profile, _settings())

        assert effective.persona is None
        assert effective.sources["persona"] == "unset"
