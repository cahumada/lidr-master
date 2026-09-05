"""POST /answer with retrieval and the LLM mocked.

No database and no network: this tests the endpoint contract — what comes
back, what the defaults are, what is rejected — not answer quality, which
is measured in ``scripts/eval_generation.py`` against the golden set.

|| POST /answer con la recuperación y el LLM mockeados. Sin base y sin red:
esto prueba el contrato del endpoint —qué vuelve, cuáles son los defaults,
qué se rechaza— no la calidad de la respuesta, que se mide en
``scripts/eval_generation.py`` contra el golden set.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_embedder, get_reranker
from app.domain.profiles import ProfileResolutionError
from app.foundation.persistence.database import get_async_session
from app.generation.rag.answer import INSUFFICIENT_CONTEXT_MESSAGE
from app.generation.rag.retrieval.hybrid import RetrievalResult, RetrievedChunk
from app.main import app


class FakeRetriever:
    def __init__(self, result: RetrievalResult | None = None) -> None:
        self.calls: list[dict] = []
        self.result = result or RetrievalResult(
            chunks=[
                RetrievedChunk(
                    content_hash="h1",
                    chunk_id="CA014::Validaciones::0",
                    document_id="CA014",
                    document_title="Coberturas de la poliza individual",
                    section="Validaciones",
                    bullet_path="Capital > Limites",
                    module_code="CA",
                    document_kind="content",
                    text="El capital asegurado no puede superar el maximo del plan.",
                    score=0.031,
                    branches=["vector", "exact"],
                    ranks={"vector": 1, "exact": 3},
                )
            ],
            branch_counts={"vector": 100, "exact": 12},
            identifier_terms=["CA014"],
        )

    async def retrieve(self, query, filters, **kwargs):
        self.calls.append({"query": query, "filters": filters, **kwargs})
        return self.result


class FakeLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self.text


@pytest.fixture
def retriever(monkeypatch) -> FakeRetriever:
    fake = FakeRetriever()
    monkeypatch.setattr("app.api.answer.HybridRetriever", lambda *a, **k: fake)
    return fake


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM(
        "El capital asegurado no puede superar el máximo del plan. [CA014 · Validaciones]"
    )


def _use_llm(monkeypatch, llm: FakeLLM, persona: str | None = None) -> None:
    """Patch the one seam the router resolves its LLM and persona through.

    ``synthesizer_runtime`` reads the ``answer_synthesizer`` profile from the
    database and builds an OpenAI client for whatever it says; these tests
    have neither, and the endpoint contract does not depend on either.

    || Parchea el único punto por donde el router resuelve su LLM y su
    persona. ``synthesizer_runtime`` lee el perfil de la base y arma un
    cliente de OpenAI con lo que diga; estos tests no tienen ninguno de los
    dos, y el contrato del endpoint no depende de eso.
    """

    async def _runtime(session, settings, *, profile_id=None):
        return llm, persona, None

    monkeypatch.setattr("app.api.answer.synthesizer_runtime", _runtime)


@pytest.fixture
def client(retriever, llm):
    async def no_session():
        yield None

    app.dependency_overrides[get_async_session] = no_session
    app.dependency_overrides[get_embedder] = lambda: object()
    app.dependency_overrides[get_reranker] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_the_answer_carries_the_retrieved_citations(client, monkeypatch, llm):
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    _use_llm(monkeypatch, llm)

    body = client.post("/answer", json={"question": "tope de capital"}).json()

    assert body["question"] == "tope de capital"
    assert "CA014" in body["answer"]
    assert body["grounded"] is True
    citation = body["citations"][0]
    assert citation["document_id"] == "CA014"
    assert citation["section"] == "Validaciones"
    assert citation["bullet_path"] == "Capital > Limites"
    assert citation["content_hash"] == "h1"


def test_an_invented_citation_marks_ungrounded_and_does_not_reject(
    client, monkeypatch, llm
):
    """citations stay the retrieved hits; grounded tells the prose invented one."""
    llm.text = "Según [ZZ999 · Función] el campo es obligatorio."
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    _use_llm(monkeypatch, llm)

    response = client.post("/answer", json={"question": "tope de capital"})

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert [hit["document_id"] for hit in body["citations"]] == ["CA014"]


def test_empty_retrieval_does_not_call_the_llm(client, monkeypatch, retriever, llm):
    retriever.result = RetrievalResult(chunks=[])
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    _use_llm(monkeypatch, llm)

    body = client.post("/answer", json={"question": "algo que no existe"}).json()

    assert body["answer"] == INSUFFICIENT_CONTEXT_MESSAGE
    assert body["citations"] == []
    assert body["grounded"] is True
    assert llm.calls == []


def test_the_defaults_are_the_measured_pipeline(client, retriever, monkeypatch, llm):
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: "un-reranker")
    _use_llm(monkeypatch, llm)

    client.post("/answer", json={"question": "tope de capital"})

    call = retriever.calls[0]
    assert call["max_per_document"] == 1
    assert call["decompose_query"] is True
    assert call["reranker"] == "un-reranker"
    assert call["branches"] == ("vector", "exact")
    assert call["limit"] == 10


def test_the_filters_reach_the_repository(client, retriever, monkeypatch, llm):
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    _use_llm(monkeypatch, llm)

    client.post(
        "/answer",
        json={
            "question": "transacciones masivas",
            "module_code": ["CA"],
            "window_type_name": ["Masivo con encabezado"],
        },
    )

    filters = retriever.calls[0]["filters"]
    assert filters.module_code == ["CA"]
    assert filters.window_type_name == ["Masivo con encabezado"]


def test_lexical_on_adds_the_third_branch(client, retriever, monkeypatch, llm):
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    _use_llm(monkeypatch, llm)

    client.post("/answer", json={"question": "tope de capital", "lexical": True})

    assert retriever.calls[0]["branches"] == ("vector", "lexical", "exact")


def test_a_one_character_question_is_rejected(client):
    """The input guardrail is the schema's min_length=2, same as /search."""
    assert client.post("/answer", json={"question": "a"}).status_code == 422


def test_the_prompt_the_llm_sees_carries_provenance(client, monkeypatch, llm):
    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    _use_llm(monkeypatch, llm)

    client.post("/answer", json={"question": "tope de capital"})

    assert "[CA014 · Validaciones]" in llm.calls[0]["user"]
    assert "[document_id · section]" in llm.calls[0]["system"]


def test_an_unknown_profile_id_is_refused(client, monkeypatch, llm):
    async def _runtime(session, settings, *, profile_id=None):
        if profile_id:
            raise ProfileResolutionError(
                f"No profile {profile_id!r}. || No existe el perfil {profile_id!r}."
            )
        return llm, None, None

    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    monkeypatch.setattr("app.api.answer.synthesizer_runtime", _runtime)

    response = client.post(
        "/answer", json={"question": "tope de capital", "profile_id": "missing"}
    )

    assert response.status_code == 422
    assert "perfil" in response.json()["detail"]


def test_a_profile_id_is_forwarded_to_the_runtime(client, monkeypatch, llm):
    seen: list[str | None] = []

    async def _runtime(session, settings, *, profile_id=None):
        seen.append(profile_id)
        return llm, "Sé breve.", None

    monkeypatch.setattr("app.api.answer.get_reranker", lambda: None)
    monkeypatch.setattr("app.api.answer.synthesizer_runtime", _runtime)

    response = client.post(
        "/answer", json={"question": "tope de capital", "profile_id": "abc-1"}
    )

    assert response.status_code == 200
    assert seen == ["abc-1"]
