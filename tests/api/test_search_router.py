"""GET /search con la capa de recuperación mockeada.

Sin base y sin red: lo que se prueba acá es el contrato del endpoint —qué
procedencia sale, qué defaults tiene, qué rechaza— y no la calidad de la
búsqueda, que se mide en `scripts/eval_retrieval.py` contra el golden set.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_embedder, get_reranker
from app.foundation.persistence.database import get_async_session
from app.generation.rag.retrieval.hybrid import RetrievalResult, RetrievedChunk
from app.main import app


class FakeRetriever:
    """Registra con qué lo llamaron y devuelve un resultado fijo."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def retrieve(self, query, filters, **kwargs):
        self.calls.append({"query": query, "filters": filters, **kwargs})
        return RetrievalResult(
            chunks=[
                RetrievedChunk(
                    content_hash="h1",
                    chunk_id="CA014::coberturas::0",
                    document_id="CA014",
                    document_title="Coberturas de la poliza individual",
                    section="Validaciones",
                    bullet_path="Capital > Limites",
                    module_code="CA",
                    text="El capital asegurado no puede superar el maximo del plan.",
                    score=0.031,
                    branches=["vector", "exact"],
                    ranks={"vector": 1, "exact": 3},
                )
            ],
            branch_counts={"vector": 100, "exact": 12},
            identifier_terms=["CA014"],
        )


@pytest.fixture
def retriever(monkeypatch) -> FakeRetriever:
    fake = FakeRetriever()
    monkeypatch.setattr("app.api.search.HybridRetriever", lambda *a, **k: fake)
    return fake


@pytest.fixture
def client(retriever):
    async def no_session():
        yield None

    app.dependency_overrides[get_async_session] = no_session
    app.dependency_overrides[get_embedder] = lambda: object()
    app.dependency_overrides[get_reranker] = lambda: object()
    # `get_reranker` is called directly and not through Depends, so the override
    # above does not reach it. Patched where it is used.
    # || `get_reranker` se llama directo y no por Depends, así que el override de
    # arriba no le llega. Se parchea donde se usa.
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_a_hit_carries_its_provenance(client, monkeypatch):
    """Documento, sección, breadcrumb y de qué camino vino. Son reglas de
    negocio de seguros: una respuesta que no se puede verificar contra su
    documento no sirve."""
    monkeypatch.setattr("app.api.search.get_reranker", lambda: None)

    body = client.get("/search", params={"q": "limites de capital"}).json()

    hit = body["hits"][0]
    assert hit["document_id"] == "CA014"
    assert hit["section"] == "Validaciones"
    assert hit["bullet_path"] == "Capital > Limites"
    assert hit["branches"] == ["vector", "exact"]
    assert hit["ranks"] == {"vector": 1, "exact": 3}
    assert hit["content_hash"] == "h1"


def test_the_response_says_how_it_was_produced(client, monkeypatch):
    """Dos listas de resultados iguales producidas por pipelines distintos son
    indistinguibles sin esto."""
    monkeypatch.setattr("app.api.search.get_reranker", lambda: None)

    body = client.get("/search", params={"q": "limites de capital"}).json()

    assert body["query"] == "limites de capital"
    assert body["count"] == 1
    assert body["branch_counts"] == {"vector": 100, "exact": 12}
    assert body["identifier_terms"] == ["CA014"]


def test_a_compound_question_reports_its_sub_queries(client, monkeypatch):
    monkeypatch.setattr("app.api.search.get_reranker", lambda: None)
    question = (
        "Si un recibo tiene via de cobro PAC, ¿como se gestiona la domiciliacion, "
        "de que manera afecta al boletin y que controles hay para traspasar el pago?"
    )

    body = client.get("/search", params={"q": question}).json()

    assert len(body["sub_queries"]) == 3
    assert all("PAC" in sub for sub in body["sub_queries"])


def test_a_simple_question_reports_no_sub_queries(client, monkeypatch):
    """Vacío es el caso común: 11 de las 15 preguntas que el divisor deja
    enteras son de un solo documento."""
    monkeypatch.setattr("app.api.search.get_reranker", lambda: None)

    body = client.get("/search", params={"q": "que hace la transaccion CA014"}).json()

    assert body["sub_queries"] == []


def test_the_defaults_are_the_measured_pipeline(client, retriever, monkeypatch):
    """Los defaults son la configuración medida como mejor, no las más baratas:
    `cap=1`, descomposición y reranker. La rama léxica queda apagada porque
    medida baja el acierto@1 de 77% a 48%."""
    monkeypatch.setattr("app.api.search.get_reranker", lambda: "un-reranker")

    client.get("/search", params={"q": "limites de capital"})

    call = retriever.calls[0]
    assert call["max_per_document"] == 1
    assert call["decompose_query"] is True
    assert call["reranker"] == "un-reranker"
    assert call["branches"] == ("vector", "exact")


def test_rerank_off_passes_no_reranker(client, retriever, monkeypatch):
    monkeypatch.setattr("app.api.search.get_reranker", lambda: "un-reranker")

    client.get("/search", params={"q": "limites de capital", "rerank": "false"})

    assert retriever.calls[0]["reranker"] is None


def test_lexical_on_adds_the_third_branch(client, retriever, monkeypatch):
    monkeypatch.setattr("app.api.search.get_reranker", lambda: None)

    client.get("/search", params={"q": "limites de capital", "lexical": "true"})

    assert retriever.calls[0]["branches"] == ("vector", "lexical", "exact")


def test_the_filters_reach_the_repository(client, retriever, monkeypatch):
    monkeypatch.setattr("app.api.search.get_reranker", lambda: None)

    client.get(
        "/search",
        params={
            "q": "transacciones masivas",
            "module_code": "CA",
            "window_type_name": "Masivo con encabezado",
        },
    )

    filters = retriever.calls[0]["filters"]
    assert filters.module_code == "CA"
    assert filters.window_type_name == "Masivo con encabezado"


def test_a_query_of_one_character_is_rejected(client):
    """Una consulta de un caracter no puede recuperar nada útil y cuesta lo
    mismo que una real."""
    assert client.get("/search", params={"q": "a"}).status_code == 422


def test_a_limit_over_the_cap_is_rejected(client):
    assert client.get("/search", params={"q": "capital", "limit": 500}).status_code == 422
