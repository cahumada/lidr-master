"""Tests for POST /answer/agentic with graph mocked.

|| Tests de POST /answer/agentic con el grafo mockeado.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.answer import router as answer_router
from app.api.answer_agentic import router as answer_agentic_router
from app.api.corpus import router as corpus_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.dependencies import get_answer_llm, get_embedder, get_reranker
from app.foundation.persistence.database import get_async_session


class FakeSnapshot:
    def __init__(self, values, *, next_nodes=(), interrupts=()):
        self.values = values
        self.next = next_nodes
        self.interrupts = interrupts


class FakeGraph:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    async def ainvoke(self, payload, config):
        self.calls.append((payload, config))
        return self.snapshot.values

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
    test_app.dependency_overrides[get_answer_llm] = lambda: object()

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
    test_app.dependency_overrides[get_answer_llm] = lambda: object()

    with TestClient(test_app) as client:
        response = client.post("/answer/agentic", json={"question": "fuera del corpus"})
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "awaiting_human_review"
        assert body["review_reasons"]

    test_app.dependency_overrides.clear()
