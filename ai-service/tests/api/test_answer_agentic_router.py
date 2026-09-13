"""Tests for POST /answer/agentic with graph mocked.

|| Tests de POST /answer/agentic con el grafo mockeado.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.answer_agentic as answer_agentic_module
from app.api.answer import router as answer_router
from app.api.answer_agentic import router as answer_agentic_router
from app.api.corpus import router as corpus_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.dependencies import get_embedder, get_reranker
from app.foundation.persistence.database import get_async_session


class FakeSnapshot:
    def __init__(self, values, *, next_nodes=(), interrupts=()):
        self.values = values
        self.next = next_nodes
        self.interrupts = interrupts


class FakeGraph:
    def __init__(self, snapshot, *, stream_updates=None):
        self.snapshot = snapshot
        self.calls = []
        # Each item is a dict with one key (the node name) mapping to its
        # partial-state update, matching what `astream(..., stream_mode=
        # "updates")` yields for real. || Cada item es un dict con una clave
        # (el nombre del nodo) que mapea a su update parcial de estado.
        self.stream_updates = stream_updates or []

    async def ainvoke(self, payload, config):
        self.calls.append((payload, config))
        return self.snapshot.values

    async def astream(self, payload, config, stream_mode="updates"):
        self.calls.append((payload, config, stream_mode))
        for update in self.stream_updates:
            yield update

    async def aget_state(self, config):
        return self.snapshot


@asynccontextmanager
async def _test_lifespan(app: FastAPI):
    app.state.answer_graph = getattr(app.state, "answer_graph", None)
    yield


def _test_app(snapshot: FakeSnapshot) -> FastAPI:
    test_app = FastAPI(lifespan=_test_lifespan)
    test_app.include_router(documents_router)
    test_app.include_router(search_router)
    test_app.include_router(answer_router)
    test_app.include_router(answer_agentic_router)
    test_app.include_router(corpus_router)
    test_app.state.answer_graph = FakeGraph(snapshot)
    return test_app


@pytest.fixture
def client():
    async def no_session():
        yield None

    snapshot = FakeSnapshot(
        {
            "query": "test",
            "answer": "respuesta",
            "citations": [],
            "citations_valid": True,
            "confidence": 0.9,
            "routing_history": [],
        }
    )
    test_app = _test_app(snapshot)
    test_app.dependency_overrides[get_async_session] = no_session
    test_app.dependency_overrides[get_embedder] = lambda: object()
    test_app.dependency_overrides[get_reranker] = lambda: None

    with TestClient(test_app) as test_client:
        yield test_client
    test_app.dependency_overrides.clear()


def test_completed_run_returns_200(client):
    response = client.post("/answer/agentic", json={"question": "test"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["answer"] == "respuesta"


def test_paused_run_returns_202():
    async def no_session():
        yield None

    interrupt = type("I", (), {"value": {"reasons": ["no evidence"]}})()
    snapshot = FakeSnapshot(
        {
            "query": "fuera",
            "answer": "sin info",
            "citations": [],
            "confidence": 0.1,
        },
        next_nodes=("answer_review_gate",),
        interrupts=(interrupt,),
    )
    test_app = _test_app(snapshot)
    test_app.dependency_overrides[get_async_session] = no_session
    test_app.dependency_overrides[get_embedder] = lambda: object()
    test_app.dependency_overrides[get_reranker] = lambda: None

    with TestClient(test_app) as client:
        response = client.post("/answer/agentic", json={"question": "fuera del corpus"})
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "awaiting_human_review"
        assert body["review_reasons"]

    test_app.dependency_overrides.clear()


# --- filtros efectivos en el contrato HTTP -----------------------------


def test_effective_filters_travel_with_their_source():
    """What was applied, and why. A filter applied without saying so is a defect.

    || Lo que se aplicó, y por qué. Un filtro aplicado sin decirlo es un defecto.
    """

    async def no_session():
        yield None

    snapshot = FakeSnapshot(
        {
            "query": "test",
            "answer": "respuesta",
            "citations": [],
            "citations_valid": True,
            "confidence": 0.9,
            "routing_history": [],
            "filters": {"module_code": ["CA"]},
            "filter_sources": {"module_code": "request"},
        }
    )
    test_app = _test_app(snapshot)
    test_app.dependency_overrides[get_async_session] = no_session
    test_app.dependency_overrides[get_embedder] = lambda: object()
    test_app.dependency_overrides[get_reranker] = lambda: None

    with TestClient(test_app) as test_client:
        body = test_client.post(
            "/answer/agentic", json={"question": "test", "module_code": ["CA"]}
        ).json()

    assert body["effective_filters"] == [
        {"field": "module_code", "values": ["CA"], "source": "request"}
    ]
    test_app.dependency_overrides.clear()


def test_without_filters_the_field_is_empty_not_absent(client):
    """The no-filter path is the one every eval uses: it must not change shape.

    || El camino sin filtros es el que usan todos los evals: no puede cambiar
    de forma.
    """
    body = client.post("/answer/agentic", json={"question": "test"}).json()

    assert body["effective_filters"] == []


# --------------------------------------------------------------------------
# Ownership || Pertenencia
#
# The session routes are not the only door into a conversation: a turn posted
# with somebody else's `session_id` would read their memory and append to their
# transcript. What has to hold here is that the caller's identity reaches the
# store this router builds — the store is what refuses the foreign id, and
# `tests/generation/conversation/test_store.py` proves that part.
#
# || Las rutas de sesión no son la única puerta a una conversación: un turno
# mandado con el `session_id` de otro leería su memoria y escribiría en su
# transcript. Acá lo que tiene que valer es que la identidad de quien llama
# LLEGUE al store que arma este router.
# --------------------------------------------------------------------------


def _owners_seen(monkeypatch) -> list[str | None]:
    """Record the ``owner_id`` every ``SessionStore`` in this router is built with.

    || Registra el ``owner_id`` con el que se arma cada ``SessionStore``.
    """
    seen: list[str | None] = []

    class RecordingStore:
        """Records the owner and behaves like a store with nothing in it.

        Returning ``None`` from ``get`` is not a shortcut: it is exactly what
        the real store does for an id that is not this owner's, and it is the
        behavior that keeps the turn from touching the conversation.

        || Registra el dueño y se comporta como un store vacío. Devolver
        ``None`` en ``get`` no es un atajo: es justo lo que hace el store real
        con un id que no es de este dueño.
        """

        def __init__(self, session, *, ttl_days, owner_id):
            seen.append(owner_id)

        async def get(self, session_id):
            return None

        async def save(self, conversation):
            raise AssertionError("a foreign conversation must never be written")

    monkeypatch.setattr(answer_agentic_module, "SessionStore", RecordingStore)
    return seen


def test_a_turn_carries_the_callers_identity_into_the_store(client, monkeypatch):
    seen = _owners_seen(monkeypatch)

    client.post(
        "/answer/agentic",
        json={"question": "test", "session_id": "no-importa"},
        headers={"X-Console-User": "user_ada"},
    )

    assert seen == ["user_ada"]


def test_a_turn_without_identity_does_not_reach_an_owned_conversation(
    client, monkeypatch
):
    """No header means the ownerless bucket, not everybody's conversations.

    || Sin header se cae al balde sin dueño, no a las conversaciones de todos.
    """
    seen = _owners_seen(monkeypatch)

    client.post("/answer/agentic", json={"question": "test", "session_id": "no-importa"})

    assert seen == [None]
