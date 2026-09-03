"""Tests for POST /answer/agentic/start + GET .../progress, graph mocked.

``get_activity_log()`` is a process-wide ``lru_cache`` singleton called
directly (not via ``Depends``) by the router — same as ``get_embedder()``/
``get_reranker()``/``get_answer_llm()`` in this file. It is not overridden
here for the same reason those are not really overridable either: a direct
call bypasses ``dependency_overrides`` entirely. That is safe for these
tests because every run gets its own random ``thread_id`` (``uuid4``), so
sharing the one real log across tests never collides.

|| Tests de POST /answer/agentic/start + GET .../progress, con el grafo
mockeado. ``get_activity_log()`` es un singleton de proceso llamado directo
(no vía ``Depends``) — igual que el resto de las dependencias de este
archivo. Es seguro para estos tests porque cada corrida tiene su propio
``thread_id`` al azar.
"""

from __future__ import annotations

import time
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


class FakeStreamingGraph:
    """Fake graph whose ``astream`` yields canned per-node updates.

    || Grafo falso cuyo ``astream`` produce updates por nodo enlatados.
    """

    def __init__(self, snapshot: FakeSnapshot, *, updates: list[dict] | None = None):
        self.snapshot = snapshot
        self.updates = updates or []

    async def astream(self, payload, config, stream_mode="updates"):
        for update in self.updates:
            yield update

    async def aget_state(self, config):
        return self.snapshot


@asynccontextmanager
async def _test_lifespan(app: FastAPI):
    app.state.answer_graph = getattr(app.state, "answer_graph", None)
    yield


def _test_app(graph) -> FastAPI:
    test_app = FastAPI(lifespan=_test_lifespan)
    test_app.include_router(documents_router)
    test_app.include_router(search_router)
    test_app.include_router(answer_router)
    test_app.include_router(answer_agentic_router)
    test_app.include_router(corpus_router)
    test_app.state.answer_graph = graph
    return test_app


def _override_deps(test_app: FastAPI) -> None:
    async def no_session():
        yield None

    test_app.dependency_overrides[get_async_session] = no_session
    test_app.dependency_overrides[get_embedder] = lambda: object()
    test_app.dependency_overrides[get_reranker] = lambda: None
    test_app.dependency_overrides[get_answer_llm] = lambda: object()


def _poll_until_finished(client: TestClient, thread_id: str, *, attempts: int = 50):
    """Poll ``/progress`` until it leaves ``running``, or fail after ``attempts``.

    The background task runs on the TestClient's own event-loop thread, so a
    little real wall-clock polling — not a single immediate read — is what
    makes this deterministic instead of racy.

    || Sondea ``/progress`` hasta que deja ``running``, o falla tras
    ``attempts``. La tarea en background corre en el thread del propio loop
    de TestClient, así que sondear un poco de tiempo real es lo que hace esto
    determinístico y no una carrera.
    """
    for _ in range(attempts):
        response = client.get(f"/answer/agentic/{thread_id}/progress")
        assert response.status_code == 200
        body = response.json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    pytest.fail("background run never left 'running'")


def test_start_returns_202_with_thread_id():
    snapshot = FakeSnapshot({"query": "test", "answer": "respuesta", "citations": []})
    test_app = _test_app(FakeStreamingGraph(snapshot))
    _override_deps(test_app)

    with TestClient(test_app) as client:
        response = client.post("/answer/agentic/start", json={"question": "test"})
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "running"
        assert body["thread_id"]

    test_app.dependency_overrides.clear()


def test_progress_reports_activity_then_completes():
    updates = [
        {"orchestrator": {"next_agent": "query_planner", "routing_history": [{"source": "fallback"}]}},
        {"query_planner": {"sub_queries": ["test"], "filters": {}}},
        {"orchestrator": {"next_agent": "evidence_retriever", "routing_history": [{"source": "fallback"}]}},
        {
            "evidence_retriever": {
                "hits": [
                    {
                        "chunk_id": "1",
                        "content_hash": "h1",
                        "document_id": "CA014",
                        "text": "x",
                        "score": 1.0,
                    }
                ]
            }
        },
    ]
    snapshot = FakeSnapshot(
        {
            "query": "test",
            "answer": "respuesta citada",
            "citations": [
                {"chunk_id": "1", "content_hash": "h1", "document_id": "CA014", "text": "x", "score": 1.0}
            ],
            "citations_valid": True,
            "confidence": 0.9,
            "routing_history": [],
        }
    )
    test_app = _test_app(FakeStreamingGraph(snapshot, updates=updates))
    _override_deps(test_app)

    with TestClient(test_app) as client:
        start = client.post("/answer/agentic/start", json={"question": "test"})
        thread_id = start.json()["thread_id"]

        body = _poll_until_finished(client, thread_id)
        assert body["status"] == "completed"
        assert body["answer"] == "respuesta citada"
        assert len(body["citations"]) == 1
        # Activity narrated at least the two orchestrator hops and the two
        # agent updates fed in.
        # || La actividad narró al menos los dos saltos del orquestador y las
        # dos actualizaciones de agente alimentadas.
        assert len(body["activity"]) >= 4
        assert any("query_planner" in entry["message"] for entry in body["activity"])

    test_app.dependency_overrides.clear()


def test_progress_reports_awaiting_human_review():
    interrupt = type("I", (), {"value": {"reasons": ["no evidence"]}})()
    snapshot = FakeSnapshot(
        {"query": "fuera", "answer": "sin info", "citations": [], "confidence": 0.1},
        next_nodes=("answer_review_gate",),
        interrupts=(interrupt,),
    )
    updates = [{"__interrupt__": (interrupt,)}]
    test_app = _test_app(FakeStreamingGraph(snapshot, updates=updates))
    _override_deps(test_app)

    with TestClient(test_app) as client:
        start = client.post("/answer/agentic/start", json={"question": "fuera del corpus"})
        thread_id = start.json()["thread_id"]

        body = _poll_until_finished(client, thread_id)
        assert body["status"] == "awaiting_human_review"
        assert body["review_reasons"] == ["no evidence"]

    test_app.dependency_overrides.clear()


def test_progress_unknown_thread_id_returns_404():
    snapshot = FakeSnapshot({"query": "test", "answer": "x", "citations": []})
    test_app = _test_app(FakeStreamingGraph(snapshot))
    _override_deps(test_app)

    with TestClient(test_app) as client:
        response = client.get("/answer/agentic/does-not-exist/progress")
        assert response.status_code == 404

    test_app.dependency_overrides.clear()


def test_progress_reports_failure():
    class BoomingGraph(FakeStreamingGraph):
        async def astream(self, payload, config, stream_mode="updates"):
            raise RuntimeError("boom")
            yield {}  # pragma: no cover — unreachable, keeps this an async generator.

    test_app = _test_app(BoomingGraph(FakeSnapshot({})))
    _override_deps(test_app)

    with TestClient(test_app) as client:
        start = client.post("/answer/agentic/start", json={"question": "test"})
        thread_id = start.json()["thread_id"]

        body = _poll_until_finished(client, thread_id)
        assert body["status"] == "failed"
        assert "boom" in body["error"]

    test_app.dependency_overrides.clear()
