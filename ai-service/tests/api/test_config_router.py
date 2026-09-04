"""Tests for GET/PUT/DELETE /config with the profile store faked.

|| Tests de GET/PUT/DELETE /config con el store de perfiles falseado.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.config import router as config_router
from app.config import Settings
from app.domain.profiles import AgentProfileRow
from app.foundation.persistence.database import get_async_session


class FakeProfileRepository:
    """In-memory stand-in, shared by every instance of a test run.

    || Reemplazo en memoria, compartido por cada instancia de una corrida.
    """

    rows: ClassVar[dict[str, AgentProfileRow]] = {}

    def __init__(self, session) -> None:
        self._session = session

    async def all(self) -> dict[str, AgentProfileRow]:
        return dict(self.rows)

    async def get(self, agent_key: str) -> AgentProfileRow | None:
        return self.rows.get(agent_key)

    async def upsert(self, agent_key, *, persona, provider, model, temperature, max_tokens):
        row = AgentProfileRow(
            agent_key=agent_key,
            persona=persona,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.rows[agent_key] = row
        return row

    async def delete(self, agent_key: str) -> bool:
        return self.rows.pop(agent_key, None) is not None


def _settings() -> Settings:
    """Fixed settings, so the assertions do not depend on the machine's .env.

    Anthropic and Moonshot deliberately have NO key: that is what makes the
    "provider not available" path testable, and it must not flip depending on
    whether the developer running the suite happens to have those keys.

    || Settings fijos, para que las aserciones no dependan del .env de la
    máquina. Anthropic y Moonshot a propósito SIN clave: es lo que hace
    testeable el camino de "proveedor no disponible", y no puede cambiar según
    quién corra la suite.
    """
    return Settings(
        OPENAI_API_KEY="sk-test",
        ANTHROPIC_API_KEY="",
        MOONSHOT_API_KEY="",
        ANSWER_PROVIDER="openai",
        ANSWER_MODEL="gpt-4o-mini",
        ANSWER_MAX_TOKENS=1024,
        ANSWER_TEMPERATURE=0.0,
        AGENT_PERSONA_MAX_CHARS=2000,
        ANSWER_MODEL_CATALOG=[
            "openai:gpt-4o-mini",
            "openai:gpt-4o",
            "anthropic:claude-sonnet-5",
            "moonshot:kimi-k2-0905-preview",
        ],
    )


@pytest.fixture
def client(monkeypatch):
    FakeProfileRepository.rows = {}
    monkeypatch.setattr("app.api.config.AgentProfileRepository", FakeProfileRepository)
    monkeypatch.setattr("app.api.config.get_settings", _settings)

    async def no_session():
        yield None

    test_app = FastAPI()
    test_app.include_router(config_router)
    test_app.dependency_overrides[get_async_session] = no_session

    with TestClient(test_app) as test_client:
        yield test_client
    test_app.dependency_overrides.clear()


class TestReadConfig:
    def test_lists_every_agent_with_its_tools_and_kind(self, client):
        body = client.get("/config").json()

        keys = [agent["key"] for agent in body["agents"]]
        assert "orchestrator" in keys
        assert "answer_synthesizer" in keys
        retriever = next(a for a in body["agents"] if a["key"] == "evidence_retriever")
        assert retriever["tools"] == ["search_corpus"]
        assert retriever["llm_driven"] is False

    def test_the_models_catalog_and_persona_cap_travel_with_it(self, client):
        body = client.get("/config").json()

        assert body["models"]
        assert body["persona_max_chars"] > 0

    def test_every_model_names_its_provider_and_its_capabilities(self, client):
        models = client.get("/config").json()["models"]

        assert {m["provider"] for m in models} <= {"openai", "anthropic", "moonshot"}
        for entry in models:
            assert isinstance(entry["available"], bool)
            assert isinstance(entry["supports_temperature"], bool)

    def test_the_three_providers_are_listed_with_their_key_setting(self, client):
        providers = client.get("/config").json()["providers"]

        by_id = {p["id"]: p for p in providers}
        assert set(by_id) == {"openai", "anthropic", "moonshot"}
        assert by_id["anthropic"]["api_key_setting"] == "ANTHROPIC_API_KEY"
        assert by_id["moonshot"]["label"] == "Moonshot (Kimi)"

    def test_claude_models_are_reported_as_rejecting_temperature(self, client):
        models = client.get("/config").json()["models"]

        sonnet = next((m for m in models if m["model"] == "claude-sonnet-5"), None)
        assert sonnet is not None
        assert sonnet["supports_temperature"] is False

    def test_only_llm_driven_agents_carry_an_effective_config(self, client):
        body = client.get("/config").json()

        for agent in body["agents"]:
            if agent["llm_driven"]:
                assert agent["effective"]["model"]
                assert agent["effective"]["sources"]["model"] in {"settings", "profile"}
            else:
                assert agent["effective"] is None


class TestUpdateProfile:
    def test_a_persona_and_a_model_are_stored_and_reported_as_overrides(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={
                "persona": "Respondé como un analista funcional.",
                "provider": "openai",
                "model": "gpt-4o",
            },
        )

        assert response.status_code == 200
        effective = response.json()["effective"]
        assert effective["persona"] == "Respondé como un analista funcional."
        assert effective["model"] == "gpt-4o"
        assert effective["sources"]["persona"] == "profile"
        assert effective["sources"]["model"] == "profile"

    def test_the_stored_profile_shows_up_on_the_next_read(self, client):
        client.put(
            "/config/agents/answer_synthesizer",
            json={"persona": "Sé breve."},
        )

        body = client.get("/config").json()
        agent = next(a for a in body["agents"] if a["key"] == "answer_synthesizer")
        assert agent["effective"]["persona"] == "Sé breve."

    def test_nulls_clear_the_overrides_back_to_the_defaults(self, client):
        client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "openai", "model": "gpt-4o"},
        )

        response = client.put("/config/agents/answer_synthesizer", json={})

        effective = response.json()["effective"]
        assert effective["sources"]["model"] == "settings"
        assert effective["persona"] is None

    def test_an_unknown_agent_is_a_404(self, client):
        response = client.put("/config/agents/nope", json={"persona": "x"})

        assert response.status_code == 404

    def test_a_deterministic_agent_is_rejected_not_silently_stored(self, client):
        response = client.put(
            "/config/agents/query_planner", json={"persona": "Sé creativo."}
        )

        assert response.status_code == 422
        assert "determinista" in response.json()["detail"]
        assert "query_planner" not in FakeProfileRepository.rows

    def test_a_model_outside_the_catalog_is_rejected(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "openai", "model": "gpt-inventado"},
        )

        assert response.status_code == 422

    def test_a_model_under_the_wrong_provider_is_rejected(self, client):
        # `gpt-4o` exists, `anthropic` exists, and the pair does not.
        # || `gpt-4o` existe, `anthropic` existe, y el par no.
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "anthropic", "model": "gpt-4o"},
        )

        assert response.status_code == 422
        assert "catálogo" in response.json()["detail"]

    def test_a_provider_without_a_key_is_rejected_before_it_can_fail_later(self, client):
        # Anthropic is in the catalog but has no key in the test environment.
        # Rejecting here beats storing a profile whose next answer 500s.
        # || Anthropic está en el catálogo pero no tiene clave en el entorno de
        # test. Rechazar acá le gana a guardar un perfil cuya próxima
        # respuesta explota.
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "anthropic", "model": "claude-sonnet-5"},
        )

        assert response.status_code == 422
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]

    def test_a_provider_without_a_model_is_rejected(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer", json={"provider": "anthropic"}
        )

        assert response.status_code == 422
        assert "par" in response.json()["detail"]

    def test_a_persona_over_the_cap_is_rejected(self, client):
        cap = client.get("/config").json()["persona_max_chars"]

        response = client.put(
            "/config/agents/answer_synthesizer", json={"persona": "x" * (cap + 1)}
        )

        assert response.status_code == 422

    def test_temperature_outside_zero_to_two_is_rejected_by_the_schema(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer", json={"temperature": 3.5}
        )

        assert response.status_code == 422


class TestDeleteProfile:
    def test_deleting_returns_the_agent_on_its_defaults(self, client):
        client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "openai", "model": "gpt-4o"},
        )

        response = client.delete("/config/agents/answer_synthesizer")

        assert response.status_code == 200
        assert response.json()["effective"]["sources"]["model"] == "settings"
        assert FakeProfileRepository.rows == {}

    def test_deleting_a_profile_that_was_never_set_is_not_an_error(self, client):
        response = client.delete("/config/agents/answer_synthesizer")

        assert response.status_code == 200

    def test_deleting_a_deterministic_agent_is_rejected(self, client):
        response = client.delete("/config/agents/citation_validator")

        assert response.status_code == 422
