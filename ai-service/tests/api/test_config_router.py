"""Tests for /config with both stores faked. No database, no network.

The property worth guarding hardest here: **no endpoint returns a credential**.
There is a test that walks the whole response body of every provider endpoint
looking for the key, because "we never return it" is the kind of promise that
a future field added in good faith can quietly break.

|| Tests de /config con los dos stores falseados. La propiedad que más importa
cuidar: NINGÚN endpoint devuelve una credencial. Hay un test que recorre el
body entero de cada endpoint de proveedor buscando la clave, porque "nunca la
devolvemos" es la clase de promesa que un campo agregado de buena fe rompe sin
que nadie lo note.
"""

from __future__ import annotations

import json
from typing import ClassVar
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.config import router as config_router
from app.config import Settings
from app.domain.profiles import (
    DEFAULT_PROFILE_NAME,
    AgentProfileRow,
    assert_name_available,
    normalize_profile_name,
    pick_promoted_default,
)
from app.domain.providers_store import ProviderModelRow, ProviderRow
from app.foundation.persistence.database import get_async_session

STORED_KEY = "sk-stored-abcd1234"


def _settings() -> Settings:
    """Fixed settings, so assertions do not depend on the machine's .env.

    Only OpenAI has an environment key here: that is what makes both the
    "credential from env" and the "no credential" paths testable, and it must
    not flip depending on who runs the suite.

    || Settings fijos. Solo OpenAI tiene clave de entorno acá: es lo que hace
    testeables los caminos de "credencial del entorno" y "sin credencial".
    """
    return Settings(
        OPENAI_API_KEY="sk-env-openai",
        ANTHROPIC_API_KEY="",
        MOONSHOT_API_KEY="",
        SECRETS_KEY="",
        ANSWER_PROVIDER="openai",
        ANSWER_MODEL="gpt-4o-mini",
        ANSWER_MAX_TOKENS=1024,
        ANSWER_TEMPERATURE=0.0,
        AGENT_PERSONA_MAX_CHARS=2000,
    )


def _provider_rows() -> list[ProviderRow]:
    return [
        ProviderRow(
            id="openai",
            label="OpenAI",
            wire="openai_compatible",
            base_url=None,
            api_key_setting="OPENAI_API_KEY",
            enabled=True,
            note="nota de openai",
        ),
        ProviderRow(
            id="anthropic",
            label="Anthropic",
            wire="anthropic_messages",
            base_url=None,
            api_key_setting="ANTHROPIC_API_KEY",
            enabled=True,
        ),
        ProviderRow(
            id="moonshot",
            label="Moonshot (Kimi)",
            wire="openai_compatible",
            base_url="https://api.moonshot.ai/v1",
            api_key_setting="MOONSHOT_API_KEY",
            enabled=True,
        ),
    ]


def _model_rows() -> list[ProviderModelRow]:
    return [
        ProviderModelRow(
            id=1, provider_id="openai", model="gpt-4o-mini", supports_temperature=True, visible=True
        ),
        ProviderModelRow(
            id=2, provider_id="openai", model="gpt-4o", supports_temperature=True, visible=True
        ),
        ProviderModelRow(
            id=3,
            provider_id="openai",
            model="text-embedding-3-small",
            supports_temperature=True,
            visible=False,
        ),
        ProviderModelRow(
            id=4,
            provider_id="anthropic",
            model="claude-sonnet-5",
            supports_temperature=False,
            visible=True,
        ),
    ]


class FakeProfileRepository:
    rows: ClassVar[dict[str, AgentProfileRow]] = {}

    def __init__(self, session) -> None:
        self._session = session

    def _of(self, agent_key: str) -> list[AgentProfileRow]:
        return [row for row in self.rows.values() if row.agent_key == agent_key]

    async def all(self):
        grouped: dict[str, list[AgentProfileRow]] = {}
        for row in self.rows.values():
            grouped.setdefault(row.agent_key, []).append(row)
        return grouped

    async def list_for(self, agent_key):
        return self._of(agent_key)

    async def get_by_id(self, profile_id):
        return self.rows.get(profile_id)

    async def default_for(self, agent_key):
        return next((row for row in self._of(agent_key) if row.is_default), None)

    async def create(
        self,
        agent_key,
        *,
        name,
        is_default,
        persona,
        guardrails,
        provider,
        model,
        temperature,
        max_tokens,
    ):
        cleaned = normalize_profile_name(name)
        existing = self._of(agent_key)
        assert_name_available(existing, cleaned)
        if not existing:
            is_default = True
        if is_default:
            for row in existing:
                row.is_default = False
        row = AgentProfileRow(
            id=str(uuid4()),
            agent_key=agent_key,
            name=cleaned,
            is_default=is_default,
            persona=persona,
            guardrails=guardrails,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.rows[row.id] = row
        return row

    async def update(
        self,
        profile_id,
        *,
        name,
        is_default,
        persona,
        guardrails,
        provider,
        model,
        temperature,
        max_tokens,
    ):
        row = self.rows.get(profile_id)
        if row is None:
            return None
        cleaned = normalize_profile_name(name)
        assert_name_available(self._of(row.agent_key), cleaned, exclude_id=row.id)
        was_default = row.is_default
        row.name = cleaned
        row.persona = persona
        row.guardrails = guardrails
        row.provider = provider,
        row.model = model
        row.temperature = temperature
        row.max_tokens = max_tokens
        if is_default:
            for sibling in self._of(row.agent_key):
                sibling.is_default = sibling.id == row.id
        else:
            row.is_default = False
            if was_default:
                promoted = pick_promoted_default(
                    [item for item in self._of(row.agent_key) if item.id != row.id]
                )
                if promoted is not None:
                    promoted.is_default = True
        return row

    async def delete_one(self, profile_id):
        row = self.rows.pop(profile_id, None)
        if row is None:
            return None
        if row.is_default:
            promoted = pick_promoted_default(self._of(row.agent_key))
            if promoted is not None:
                promoted.is_default = True
        return row

    async def upsert(self, agent_key, *, persona, guardrails, provider, model, temperature, max_tokens):
        current = await self.default_for(agent_key)
        if current is None:
            return await self.create(
                agent_key,
                name=DEFAULT_PROFILE_NAME,
                is_default=True,
                persona=persona,
                guardrails=guardrails,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        current.persona = persona
        current.guardrails = guardrails
        current.provider = provider
        current.model = model
        current.temperature = temperature
        current.max_tokens = max_tokens
        return current

    async def delete(self, agent_key):
        victims = [key for key, row in self.rows.items() if row.agent_key == agent_key]
        if not victims:
            return False
        for key in victims:
            del self.rows[key]
        return True


class FakeProviderRepository:
    provider_rows: ClassVar[list[ProviderRow]] = []
    model_rows: ClassVar[list[ProviderModelRow]] = []

    def __init__(self, session) -> None:
        self._session = session

    async def providers(self):
        return list(self.provider_rows)

    async def provider(self, provider_id):
        return next((row for row in self.provider_rows if row.id == provider_id), None)

    async def models(self):
        return list(self.model_rows)

    async def model(self, provider_id, model):
        return next(
            (
                row
                for row in self.model_rows
                if row.provider_id == provider_id and row.model == model
            ),
            None,
        )

    async def update_provider(self, provider_id, *, label=None, base_url=None, enabled=None, note=None):
        row = await self.provider(provider_id)
        if row is None:
            return None
        if label is not None:
            row.label = label
        if base_url is not None:
            row.base_url = base_url or None
        if enabled is not None:
            row.enabled = enabled
        if note is not None:
            row.note = note or None
        return row

    async def set_api_key(self, provider_id, api_key):
        from app.foundation.secrets import encrypt, hint

        row = await self.provider(provider_id)
        if row is None:
            return None
        row.api_key_ciphertext = encrypt(api_key)
        row.api_key_hint = hint(api_key)
        return row

    async def clear_api_key(self, provider_id):
        row = await self.provider(provider_id)
        if row is None:
            return None
        row.api_key_ciphertext = None
        row.api_key_hint = None
        return row

    async def upsert_model(self, provider_id, model, *, supports_temperature=True, visible=True):
        existing = await self.model(provider_id, model)
        if existing is not None:
            return existing
        row = ProviderModelRow(
            id=len(self.model_rows) + 100,
            provider_id=provider_id,
            model=model,
            supports_temperature=supports_temperature,
            visible=visible,
        )
        self.model_rows.append(row)
        return row

    async def upsert_models(self, provider_id, entries):
        inserted = 0
        for model, supports_temperature, visible in entries:
            if await self.model(provider_id, model) is not None:
                continue
            await self.upsert_model(
                provider_id, model, supports_temperature=supports_temperature, visible=visible
            )
            inserted += 1
        return inserted

    async def update_model(self, provider_id, model, *, supports_temperature=None, visible=None):
        row = await self.model(provider_id, model)
        if row is None:
            return None
        if supports_temperature is not None:
            row.supports_temperature = supports_temperature
        if visible is not None:
            row.visible = visible
        return row

    async def delete_model(self, provider_id, model):
        row = await self.model(provider_id, model)
        if row is None:
            return False
        self.model_rows.remove(row)
        return True


@pytest.fixture
def client(monkeypatch):
    FakeProfileRepository.rows = {}
    FakeProviderRepository.provider_rows = _provider_rows()
    FakeProviderRepository.model_rows = _model_rows()

    from app.foundation import secrets

    monkeypatch.setattr("app.api.config.AgentProfileRepository", FakeProfileRepository)
    monkeypatch.setattr("app.api.config.ProviderRepository", FakeProviderRepository)
    monkeypatch.setattr("app.api.config.get_settings", _settings)
    monkeypatch.setattr("app.foundation.secrets.get_settings", _settings)
    monkeypatch.setattr("app.domain.profiles.AgentProfileRepository", FakeProfileRepository)
    secrets._fernet.cache_clear()

    async def no_session():
        yield None

    test_app = FastAPI()
    test_app.include_router(config_router)
    test_app.dependency_overrides[get_async_session] = no_session

    with TestClient(test_app) as test_client:
        yield test_client
    test_app.dependency_overrides.clear()


@pytest.fixture
def with_secrets(monkeypatch):
    """A working master key, so credential storage is enabled.

    || Una master key funcionando, así guardar credenciales está habilitado.
    """
    from cryptography.fernet import Fernet

    from app.foundation import secrets

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(secrets, "get_settings", lambda: Settings(SECRETS_KEY=key))
    secrets._fernet.cache_clear()
    yield
    secrets._fernet.cache_clear()


class TestReadConfig:
    def test_providers_come_from_the_store_with_their_wire_and_key_source(self, client):
        body = client.get("/config").json()

        by_id = {p["id"]: p for p in body["providers"]}
        assert set(by_id) == {"openai", "anthropic", "moonshot"}
        assert by_id["openai"]["key_source"] == "env"
        assert by_id["openai"]["available"] is True
        assert by_id["anthropic"]["key_source"] == "none"
        assert by_id["anthropic"]["available"] is False
        assert by_id["moonshot"]["wire"] == "openai_compatible"
        assert by_id["anthropic"]["wire"] == "anthropic_messages"

    def test_models_carry_provider_visibility_and_capability(self, client):
        models = {(m["provider"], m["model"]): m for m in client.get("/config").json()["models"]}

        assert models[("openai", "gpt-4o-mini")]["available"] is True
        assert models[("openai", "text-embedding-3-small")]["visible"] is False
        assert models[("anthropic", "claude-sonnet-5")]["supports_temperature"] is False
        # Its provider has no credential, so it is not usable even though the
        # row exists. || Su proveedor no tiene credencial.
        assert models[("anthropic", "claude-sonnet-5")]["available"] is False

    def test_the_wires_and_the_storage_flag_travel_with_it(self, client):
        body = client.get("/config").json()

        assert set(body["wires"]) == {"openai_compatible", "anthropic_messages"}
        # No SECRETS_KEY in `_settings()`, so the console must not offer a form
        # that would fail. || Sin SECRETS_KEY, la consola no debe ofrecer un
        # formulario que iba a fallar.
        assert body["credential_storage_enabled"] is False

    def test_only_llm_driven_agents_carry_an_effective_config(self, client):
        for agent in client.get("/config").json()["agents"]:
            if agent["llm_driven"]:
                assert agent["effective"]["provider"] == "openai"
                assert agent["effective"]["provider_available"] is True
            else:
                assert agent["effective"] is None

    def test_the_agent_catalog_still_reports_tools_and_kind(self, client):
        agents = {a["key"]: a for a in client.get("/config").json()["agents"]}

        assert agents["evidence_retriever"]["tools"] == ["search_corpus"]
        assert agents["evidence_retriever"]["tools_used"] == ["search_corpus"]
        assert agents["evidence_retriever"]["llm_driven"] is False
        assert agents["answer_synthesizer"]["tools"] == []
        assert agents["answer_synthesizer"]["tools_used"] == []

    def test_the_synthesizer_exposes_its_prompt_and_system_guardrails(self, client):
        body = client.get("/config").json()
        agents = {a["key"]: a for a in body["agents"]}
        synthesizer = agents["answer_synthesizer"]

        assert synthesizer["system_prompt"]
        assert "[document_id · section]" in synthesizer["system_prompt"]
        assert "SOLO" in synthesizer["system_prompt"]
        kinds = {item["id"]: item["kind"] for item in synthesizer["system_guardrails"]}
        assert kinds["cite_provenance"] == "prompt"
        assert kinds["citation_grounding"] == "code"
        assert agents["query_planner"]["system_prompt"] is None
        assert agents["query_planner"]["system_guardrails"] == []

    def test_templates_and_the_tool_catalog_travel_at_the_root(self, client):
        body = client.get("/config").json()

        assert "analista funcional senior" in body["persona_template"]
        assert "Visual Time" in body["persona_template"]
        assert "workaround" in body["guardrails_template"]
        assert body["guardrails_max_chars"] == body["persona_max_chars"]
        names = {item["name"] for item in body["tools"]}
        assert names == {"search_corpus"}
        search = body["tools"][0]
        assert search["granted_to"] == ["evidence_retriever"]
        assert search["used_by"] == ["evidence_retriever"]


class TestUpdateAgentProfile:
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
        assert effective["model"] == "gpt-4o"
        assert effective["sources"]["persona"] == "profile"
        assert effective["sources"]["model"] == "profile"

    def test_a_hidden_model_is_refused(self, client):
        # Hiding it is a decision; honouring it only in the dropdown would
        # make the API the way around it.
        # || Ocultarlo es una decisión; respetarla solo en el desplegable haría
        # de la API la forma de saltearla.
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "openai", "model": "text-embedding-3-small"},
        )

        assert response.status_code == 422
        assert "ofrecidos" in response.json()["detail"]

    def test_a_model_under_the_wrong_provider_is_refused(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "anthropic", "model": "gpt-4o"},
        )

        assert response.status_code == 422

    def test_a_provider_without_a_credential_is_refused_before_it_can_fail_later(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "anthropic", "model": "claude-sonnet-5"},
        )

        assert response.status_code == 422
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]

    def test_a_provider_without_a_model_is_refused(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer", json={"provider": "anthropic"}
        )

        assert response.status_code == 422

    def test_a_deterministic_agent_is_refused(self, client):
        response = client.put("/config/agents/query_planner", json={"persona": "x"})

        assert response.status_code == 422
        assert "determinista" in response.json()["detail"]

    def test_a_persona_over_the_cap_is_refused(self, client):
        cap = client.get("/config").json()["persona_max_chars"]

        response = client.put(
            "/config/agents/answer_synthesizer", json={"persona": "x" * (cap + 1)}
        )

        assert response.status_code == 422

    def test_operator_guardrails_are_stored_and_composed_into_the_prompt(self, client):
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={
                "persona": "Respondé como un analista funcional.",
                "guardrails": "- Advertí que los importes dependen de la póliza.",
            },
        )

        assert response.status_code == 200
        profile = response.json()["profiles"][0]
        assert profile["guardrails"] == "- Advertí que los importes dependen de la póliza."
        assert response.json()["effective"]["sources"]["guardrails"] == "profile"
        assert "Advertí que los importes" in profile["composed_system_prompt"]
        assert "Respondé como un analista funcional." in profile["composed_system_prompt"]
        assert profile["composed_system_prompt"].index("[document_id · section]") < (
            profile["composed_system_prompt"].index("Advertí que los importes")
        )

    def test_guardrails_over_the_cap_are_refused(self, client):
        cap = client.get("/config").json()["guardrails_max_chars"]

        response = client.put(
            "/config/agents/answer_synthesizer", json={"guardrails": "x" * (cap + 1)}
        )

        assert response.status_code == 422
        assert "guardrails" in response.json()["detail"]

    def test_deleting_returns_the_agent_on_its_defaults(self, client):
        client.put(
            "/config/agents/answer_synthesizer",
            json={"provider": "openai", "model": "gpt-4o"},
        )

        response = client.delete("/config/agents/answer_synthesizer")

        assert response.status_code == 200
        assert response.json()["effective"]["sources"]["model"] == "settings"


class TestProviderEndpoints:
    def test_a_provider_can_be_relabelled_and_disabled(self, client):
        response = client.put(
            "/config/providers/moonshot", json={"label": "Kimi", "enabled": False}
        )

        assert response.status_code == 200
        assert response.json()["label"] == "Kimi"
        assert response.json()["enabled"] is False

    def test_an_unknown_provider_is_a_404(self, client):
        response = client.put("/config/providers/gemini", json={"label": "Gemini"})

        assert response.status_code == 404

    def test_storing_a_key_is_refused_without_a_master_key(self, client):
        # `_settings()` has no SECRETS_KEY. Refusing beats storing it in the
        # clear. || Rechazar le gana a guardarla en claro.
        response = client.put(
            "/config/providers/anthropic/key", json={"api_key": "sk-ant-secret-1234"}
        )

        assert response.status_code == 409
        assert "SECRETS_KEY" in response.json()["detail"]

    def test_storing_a_key_reports_it_as_stored_with_only_a_hint(self, client, with_secrets):
        response = client.put(
            "/config/providers/anthropic/key", json={"api_key": STORED_KEY}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["key_source"] == "stored"
        assert body["available"] is True
        assert body["api_key_hint"] == "…1234"

    def test_no_provider_endpoint_ever_returns_the_credential(self, client, with_secrets):
        # The promise that a future field could quietly break, so it is walked
        # rather than asserted field by field.
        # || La promesa que un campo futuro podría romper sin que nadie note.
        stored = client.put("/config/providers/anthropic/key", json={"api_key": STORED_KEY})
        listing = client.get("/config")
        cleared = client.delete("/config/providers/anthropic/key")

        for response in (stored, listing, cleared):
            assert STORED_KEY not in json.dumps(response.json())
            assert "sk-env-openai" not in json.dumps(response.json())

    def test_clearing_a_stored_key_falls_back_to_no_credential(self, client, with_secrets):
        client.put("/config/providers/anthropic/key", json={"api_key": STORED_KEY})

        response = client.delete("/config/providers/anthropic/key")

        assert response.json()["key_source"] == "none"
        assert response.json()["available"] is False

    def test_an_environment_key_wins_over_a_stored_one(self, client, with_secrets):
        # A deployment using real secret management must not be silently
        # overridden by something typed into the console.
        # || Un despliegue con gestión de secretos de verdad no puede quedar
        # sobreescrito en silencio por algo tipeado en la consola.
        response = client.put("/config/providers/openai/key", json={"api_key": STORED_KEY})

        assert response.json()["key_source"] == "env"


class TestModelEndpoints:
    def test_a_model_can_be_added_with_its_capability_inferred(self, client):
        response = client.post(
            "/config/providers/anthropic/models", json={"model": "claude-opus-5"}
        )

        assert response.status_code == 200
        # Inferred from what the code knows: this generation rejects sampling.
        # || Inferida de lo que sabe el código.
        assert response.json()["supports_temperature"] is False

    def test_an_added_model_can_declare_its_own_capability(self, client):
        response = client.post(
            "/config/providers/moonshot/models",
            json={"model": "kimi-future", "supports_temperature": False},
        )

        assert response.json()["supports_temperature"] is False

    def test_a_model_can_be_hidden_without_being_deleted(self, client):
        response = client.put(
            "/config/providers/openai/models/gpt-4o", json={"visible": False}
        )

        assert response.status_code == 200
        assert response.json()["visible"] is False

    def test_a_models_capability_can_be_corrected(self, client):
        # The reason this is editable: a provider can ship a model whose
        # behaviour the code has never seen.
        # || Por esto es editable: un proveedor puede sacar un modelo cuyo
        # comportamiento el código nunca vio.
        response = client.put(
            "/config/providers/openai/models/gpt-4o", json={"supports_temperature": False}
        )

        assert response.json()["supports_temperature"] is False

    def test_updating_an_unknown_model_is_a_404(self, client):
        response = client.put(
            "/config/providers/openai/models/nope", json={"visible": False}
        )

        assert response.status_code == 404

    def test_a_model_can_be_deleted(self, client):
        response = client.delete("/config/providers/openai/models/gpt-4o")

        assert response.status_code == 204
        remaining = {m["model"] for m in client.get("/config").json()["models"]}
        assert "gpt-4o" not in remaining

    def test_deleting_an_unknown_model_is_a_404(self, client):
        assert client.delete("/config/providers/openai/models/nope").status_code == 404


class TestNamedProfiles:
    def test_creating_a_named_profile_lists_it_on_the_agent(self, client):
        response = client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "Conservador", "persona": "Sé breve y cita."},
        )

        assert response.status_code == 200
        profiles = response.json()["profiles"]
        assert len(profiles) == 1
        assert profiles[0]["name"] == "Conservador"
        assert profiles[0]["is_default"] is True
        assert profiles[0]["effective"]["sources"]["persona"] == "profile"

    def test_a_duplicate_name_is_refused(self, client):
        client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "Conservador"},
        )

        response = client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "conservador"},
        )

        assert response.status_code == 422
        assert "nombre" in response.json()["detail"]

    def test_marking_a_profile_default_unsets_the_previous_one(self, client):
        first = client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "Conservador"},
        ).json()["profiles"][0]
        second = client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "Exhaustivo", "is_default": True},
        ).json()["profiles"]

        by_name = {row["name"]: row for row in second}
        assert by_name["Exhaustivo"]["is_default"] is True
        assert by_name["Conservador"]["is_default"] is False
        assert first["id"] == by_name["Conservador"]["id"]

    def test_deleting_the_last_profile_falls_back_to_settings(self, client):
        created = client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "Conservador", "provider": "openai", "model": "gpt-4o"},
        ).json()["profiles"][0]

        response = client.delete(
            f"/config/agents/answer_synthesizer/profiles/{created['id']}"
        )

        assert response.status_code == 200
        assert response.json()["profiles"] == []
        assert response.json()["effective"]["sources"]["model"] == "settings"

    def test_a_foreign_profile_id_is_a_404(self, client):
        response = client.delete("/config/agents/answer_synthesizer/profiles/missing")

        assert response.status_code == 404

    def test_a_deterministic_agent_cannot_hold_a_named_profile(self, client):
        response = client.post(
            "/config/agents/query_planner/profiles",
            json={"name": "Nope"},
        )

        assert response.status_code == 422
        assert "determinista" in response.json()["detail"]

    def test_the_anonymous_put_is_an_alias_for_the_default_profile(self, client):
        client.post(
            "/config/agents/answer_synthesizer/profiles",
            json={"name": "Conservador", "persona": "original"},
        )
        response = client.put(
            "/config/agents/answer_synthesizer",
            json={"persona": "actualizado"},
        )

        profiles = response.json()["profiles"]
        assert len(profiles) == 1
        assert profiles[0]["name"] == "Conservador"
        assert profiles[0]["persona"] == "actualizado"

    def test_get_config_includes_the_graph_flow(self, client):
        flow = client.get("/config").json()["flow"]

        keys = {node["key"] for node in flow["nodes"]}
        assert "orchestrator" in keys
        assert "answer_synthesizer" in keys
        assert flow["ladder"] == [
            "query_planner",
            "evidence_retriever",
            "answer_synthesizer",
            "citation_validator",
        ]
        sources = {edge["source"] for edge in flow["edges"]}
        assert {"START", "orchestrator", "answer_review_gate"} <= sources

    def test_get_config_includes_the_worked_example(self, client):
        # The flow screen explains each node with one real question. It reads
        # that question from here, so a served flow without it would leave the
        # screen with nothing concrete to show.
        # || La pantalla de flujo explica cada nodo con una pregunta real y la
        # lee de acá; un flujo servido sin ella dejaría la pantalla sin nada
        # concreto que mostrar.
        flow = client.get("/config").json()["flow"]

        assert flow["example"]["question"]
        assert "golden_curated" in flow["example"]["source"]
        for node in flow["nodes"]:
            assert node["example"]["receives"]
            assert node["example"]["leaves"]

        planner = next(node for node in flow["nodes"] if node["key"] == "query_planner")
        synthesizer = next(
            node for node in flow["nodes"] if node["key"] == "answer_synthesizer"
        )
        assert len(planner["example"]["detail"]) == 3
        assert planner["example"]["caveat"] is None
        assert synthesizer["example"]["caveat"]


class TestModelRefresh:
    def test_refreshing_stores_new_ids_hidden(self, client, monkeypatch):
        # A provider's listing includes things that are not chat models, so
        # what comes back arrives hidden and a human curates it.
        # || El listado incluye cosas que no son modelos de chat.
        monkeypatch.setattr(
            "app.api.config.list_provider_models",
            lambda provider: ["gpt-4o-mini", "gpt-5-new", "whisper-1"],
        )

        response = client.post("/config/providers/openai/models/refresh")

        assert response.status_code == 200
        body = response.json()
        assert body["reported"] == 3
        assert sorted(body["added"]) == ["gpt-5-new", "whisper-1"]
        assert body["already_known"] == 1

        models = {
            m["model"]: m for m in client.get("/config").json()["models"]
        }
        assert models["gpt-5-new"]["visible"] is False

    def test_refreshing_a_provider_without_a_credential_is_refused(self, client):
        response = client.post("/config/providers/anthropic/models/refresh")

        assert response.status_code == 422

    def test_a_provider_error_is_reported_as_a_bad_gateway(self, client, monkeypatch):
        from app.foundation.llm.providers import LLMProviderError

        def _boom(provider):
            raise LLMProviderError("could not list models")

        monkeypatch.setattr("app.api.config.list_provider_models", _boom)

        response = client.post("/config/providers/openai/models/refresh")

        assert response.status_code == 502
