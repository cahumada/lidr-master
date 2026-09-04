"""Tests for GET/PUT/DELETE /config with the profile store faked.

|| Tests de GET/PUT/DELETE /config con el store de perfiles falseado.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.config import router as config_router
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

    async def upsert(self, agent_key, *, persona, model, temperature, max_tokens):
        row = AgentProfileRow(
            agent_key=agent_key,
            persona=persona,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.rows[agent_key] = row
        return row

    async def delete(self, agent_key: str) -> bool:
        return self.rows.pop(agent_key, None) is not None


@pytest.fixture
def client(monkeypatch):
    FakeProfileRepository.rows = {}
    monkeypatch.setattr("app.api.config.AgentProfileRepository", FakeProfileRepository)

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
            json={"persona": "Respondé como un analista funcional.", "model": "gpt-4o"},
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
        client.put("/config/agents/answer_synthesizer", json={"model": "gpt-4o"})

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
            "/config/agents/answer_synthesizer", json={"model": "gpt-inventado"}
        )

        assert response.status_code == 422

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
        client.put("/config/agents/answer_synthesizer", json={"model": "gpt-4o"})

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
