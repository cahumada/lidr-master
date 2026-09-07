"""The session endpoints, with the store mocked.

No database and no network: this tests the transport contract — what an
unknown id does, what a delete of something already gone does, what the view
exposes — not the persistence, which ``tests/generation/conversation/
test_store.py`` covers against a real Postgres.

|| Los endpoints de sesión con el store mockeado. Sin base y sin red: esto
prueba el contrato de transporte, no la persistencia.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.foundation.persistence.database import get_async_session
from app.generation.conversation.models import (
    Anchor,
    CitationSnapshot,
    ConversationFacts,
    ConversationSession,
    HistoryTurn,
    Turn,
)
from app.main import app


class FakeStore:
    """In-memory stand-in for ``SessionStore``. || Doble en memoria."""

    def __init__(self) -> None:
        self.sessions: dict[str, ConversationSession] = {}
        self.expired_ids: set[str] = set()

    async def create(self) -> ConversationSession:
        conversation = ConversationSession()
        self.sessions[conversation.session_id] = conversation
        return conversation

    async def get(self, session_id: str) -> ConversationSession | None:
        if session_id in self.expired_ids:
            return None
        return self.sessions.get(session_id)

    async def save(self, conversation: ConversationSession) -> None:
        self.sessions[conversation.session_id] = conversation

    async def list_recent(self, *, limit: int, offset: int) -> list[ConversationSession]:
        items = [
            item
            for item in self.sessions.values()
            if item.history and item.session_id not in self.expired_ids
        ]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items[offset : offset + limit]

    async def rename(self, session_id: str, title: str) -> ConversationSession | None:
        conversation = await self.get(session_id)
        if conversation is None:
            return None
        conversation.title = title
        return conversation

    async def delete(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None


@pytest.fixture
def store(monkeypatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr("app.api.answer_session._store", lambda session: fake)
    return fake


@pytest.fixture
def client(store):
    async def no_session():
        yield None

    app.dependency_overrides[get_async_session] = no_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_a_session_is_created_with_a_service_issued_id(client):
    """An id the service did not mint is an id it cannot validate.

    || Un id que el servicio no acuñó es un id que no puede validar.
    """
    response = client.post("/answer/session")

    assert response.status_code == 201
    assert response.json()["session_id"]


def test_a_new_session_remembers_nothing(client):
    session_id = client.post("/answer/session").json()["session_id"]

    body = client.get(f"/answer/session/{session_id}").json()

    assert body["turns"] == []
    assert body["anchors"] == []
    assert body["facts"]["last_document_ids"] == []


def test_the_view_exposes_what_the_session_remembers(client, store):
    conversation = ConversationSession(
        facts=ConversationFacts(module_code=["CA"], last_document_ids=["CA014"])
    )
    conversation.pin(
        [Anchor(kind="module_code", value="CA", source_question="solo módulo CA")]
    )
    conversation.append_turn(
        Turn(question="¿y eso?", resolved_question="¿y eso? (sobre CA014)", answer="texto"),
        max_turns=4,
    )
    store.sessions[conversation.session_id] = conversation

    body = client.get(f"/answer/session/{conversation.session_id}").json()

    assert body["facts"]["last_document_ids"] == ["CA014"]
    assert body["anchors"][0]["source_question"] == "solo módulo CA"
    assert body["turns"][0]["resolved_question"] == "¿y eso? (sobre CA014)"
    assert body["max_turns"] >= 1


def test_an_unknown_session_is_404(client):
    assert client.get("/answer/session/no-existe").status_code == 404


def test_deleting_is_idempotent(client):
    """"Start a new thread" must not fail because the old one had expired.

    || «Empezar un hilo nuevo» no puede fallar porque el anterior venció.
    """
    session_id = client.post("/answer/session").json()["session_id"]

    assert client.delete(f"/answer/session/{session_id}").status_code == 204
    assert client.delete(f"/answer/session/{session_id}").status_code == 204


def test_an_anchor_can_be_unpinned(client, store):
    conversation = ConversationSession()
    conversation.pin(
        [Anchor(kind="module_code", value="CA", source_question="solo módulo CA")]
    )
    store.sessions[conversation.session_id] = conversation

    body = client.delete(
        f"/answer/session/{conversation.session_id}/anchors/module_code/CA"
    ).json()

    assert body["anchors"] == []


def test_unpinning_on_an_unknown_session_is_404(client):
    response = client.delete("/answer/session/no-existe/anchors/module_code/CA")

    assert response.status_code == 404


def test_the_view_exposes_history_and_title_alongside_the_window(client, store):
    conversation = ConversationSession()
    for index in range(5):
        conversation.append_turn(
            Turn(
                question=f"pregunta {index}",
                resolved_question=f"pregunta {index}",
                answer=f"preview {index}",
            ),
            max_turns=4,
        )
        conversation.append_history(
            HistoryTurn(
                question=f"pregunta {index}",
                resolved_question=f"pregunta {index}",
                answer=f"respuesta entera {index}",
                citations=[
                    CitationSnapshot(
                        document_id="CA014",
                        document_title="Alta",
                        content_hash="abc",
                    )
                ]
                if index == 0
                else [],
            )
        )
    store.sessions[conversation.session_id] = conversation

    body = client.get(f"/answer/session/{conversation.session_id}").json()

    assert body["title"] == "pregunta 0"
    assert len(body["turns"]) == 4
    assert len(body["history"]) == 5
    assert body["history"][0]["answer"] == "respuesta entera 0"
    assert body["history"][0]["citations"][0]["document_id"] == "CA014"
    assert "text" not in body["history"][0]["citations"][0]
    assert "created_at" in body
    assert "updated_at" in body


def test_the_list_skips_empty_and_expired_and_respects_limit(client, store):
    empty = ConversationSession()
    store.sessions[empty.session_id] = empty

    expired = ConversationSession()
    expired.append_history(
        HistoryTurn(question="vieja", resolved_question="vieja", answer="x")
    )
    store.sessions[expired.session_id] = expired
    store.expired_ids.add(expired.session_id)

    kept: list[ConversationSession] = []
    for index in range(3):
        item = ConversationSession()
        item.append_history(
            HistoryTurn(
                question=f"viva {index}",
                resolved_question=f"viva {index}",
                answer="x",
            )
        )
        store.sessions[item.session_id] = item
        kept.append(item)

    full = client.get("/answer/sessions").json()
    ids = {row["session_id"] for row in full}
    assert empty.session_id not in ids
    assert expired.session_id not in ids
    assert {item.session_id for item in kept} <= ids
    assert all(row["turn_count"] == 1 for row in full)

    page = client.get("/answer/sessions", params={"limit": 1}).json()
    assert len(page) == 1


def test_an_empty_list_is_an_empty_array(client):
    response = client.get("/answer/sessions")

    assert response.status_code == 200
    assert response.json() == []


def test_rename_returns_the_updated_view(client, store):
    conversation = ConversationSession()
    conversation.append_history(
        HistoryTurn(question="original", resolved_question="original", answer="x")
    )
    store.sessions[conversation.session_id] = conversation

    body = client.patch(
        f"/answer/session/{conversation.session_id}",
        json={"title": "  nuevo nombre  "},
    ).json()

    assert body["title"] == "nuevo nombre"


def test_rename_of_an_unknown_session_is_404(client):
    response = client.patch("/answer/session/no-existe", json={"title": "x"})

    assert response.status_code == 404
    assert "expired" in response.json()["detail"].lower() or "desconocido" in response.json()["detail"]


def test_rename_rejects_a_blank_title(client, store):
    conversation = ConversationSession()
    store.sessions[conversation.session_id] = conversation

    empty = client.patch(f"/answer/session/{conversation.session_id}", json={"title": ""})
    spaces = client.patch(
        f"/answer/session/{conversation.session_id}", json={"title": "   "}
    )
    missing = client.patch(f"/answer/session/{conversation.session_id}", json={})

    assert empty.status_code == 422
    assert spaces.status_code == 422
    assert missing.status_code == 422
