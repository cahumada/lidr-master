"""Tests for how an agent profile merges over the service defaults.

|| Tests de cómo un perfil de agente se mezcla sobre los defaults del servicio.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.domain.profiles import (
    AgentProfileRow,
    ProfileResolutionError,
    ProfileValidationError,
    assert_name_available,
    load_synthesizer_profile,
    normalize_profile_name,
    pick_promoted_default,
    resolve_agent_config,
)


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
        assert effective.guardrails is None
        assert effective.sources == {
            "provider": "settings",
            "model": "settings",
            "temperature": "settings",
            "max_tokens": "settings",
            "persona": "unset",
            "guardrails": "unset",
        }

    def test_profile_overrides_win_and_are_reported_as_such(self):
        profile = AgentProfileRow(
            agent_key="answer_synthesizer",
            persona="Hablás como un analista funcional.",
            guardrails="- Advertí que los importes dependen de la póliza.",
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
        assert effective.guardrails == "- Advertí que los importes dependen de la póliza."
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

    def test_a_blank_guardrails_reads_as_unset(self):
        profile = AgentProfileRow(agent_key="answer_synthesizer", guardrails="")

        effective = resolve_agent_config(profile, _settings())

        assert effective.guardrails is None
        assert effective.sources["guardrails"] == "unset"

    def test_stored_guardrails_are_an_override(self):
        profile = AgentProfileRow(
            agent_key="answer_synthesizer",
            guardrails="- No recomiendes un workaround.",
        )

        effective = resolve_agent_config(profile, _settings())

        assert effective.guardrails == "- No recomiendes un workaround."
        assert effective.sources["guardrails"] == "profile"
        assert effective.sources["persona"] == "unset"


class TestNamedProfileHelpers:
    def test_a_blank_name_is_rejected(self):
        with pytest.raises(ProfileValidationError):
            normalize_profile_name("   ")

    def test_a_duplicate_name_is_rejected_case_insensitively(self):
        existing = [AgentProfileRow(id="1", agent_key="answer_synthesizer", name="Conservador")]

        with pytest.raises(ProfileValidationError):
            assert_name_available(existing, "conservador")

    def test_renaming_a_profile_to_its_own_name_is_allowed(self):
        existing = [AgentProfileRow(id="1", agent_key="answer_synthesizer", name="Conservador")]

        assert_name_available(existing, "Conservador", exclude_id="1")

    def test_deleting_the_default_promotes_the_most_recent_sibling(self):
        older = AgentProfileRow(
            id="old",
            agent_key="answer_synthesizer",
            name="A",
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        newer = AgentProfileRow(
            id="new",
            agent_key="answer_synthesizer",
            name="B",
            updated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        assert pick_promoted_default([older, newer]) is newer

    def test_an_empty_list_promotes_nothing(self):
        assert pick_promoted_default([]) is None


class TestLoadSynthesizerProfile:
    def test_an_unknown_id_is_an_error_not_a_fallback(self, monkeypatch):
        class _Repo:
            def __init__(self, session) -> None:
                pass

            async def get_by_id(self, profile_id):
                return None

        monkeypatch.setattr("app.domain.profiles.AgentProfileRepository", _Repo)

        with pytest.raises(ProfileResolutionError):
            asyncio.run(load_synthesizer_profile(None, profile_id="missing"))

    def test_a_profile_of_another_agent_is_refused(self, monkeypatch):
        foreign = AgentProfileRow(id="x", agent_key="query_planner", name="Nope")

        class _Repo:
            def __init__(self, session) -> None:
                pass

            async def get_by_id(self, profile_id):
                return foreign

        monkeypatch.setattr("app.domain.profiles.AgentProfileRepository", _Repo)

        with pytest.raises(ProfileResolutionError):
            asyncio.run(load_synthesizer_profile(None, profile_id="x"))

    def test_absent_id_uses_the_default(self, monkeypatch):
        default = AgentProfileRow(
            id="d", agent_key="answer_synthesizer", name="Default", is_default=True
        )

        class _Repo:
            def __init__(self, session) -> None:
                pass

            async def default_for(self, agent_key):
                return default

        monkeypatch.setattr("app.domain.profiles.AgentProfileRepository", _Repo)

        assert asyncio.run(load_synthesizer_profile(None)) is default
