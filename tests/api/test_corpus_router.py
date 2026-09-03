"""POST /corpus/rebuild y sus guardas, sin base y sin corpus.

Lo que se prueba acá es el contrato del endpoint: qué rechaza, en qué orden
corren los pasos, y qué se le pasa al runner. El pipeline en sí se prueba
corriéndolo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.foundation.persistence.database import get_async_session
from app.ingestion.jobs import RUNNING, IngestionJobRow
from app.ingestion.runner import CHUNK, EMBED, LOAD, RESET, ordered
from app.main import app

# --- El orden de los pasos -----------------------------------------------------


def test_the_steps_run_in_the_only_order_that_works():
    """Embeber un corpus que todavía no se troceó no es una preferencia, es un
    error. Se ordena acá para que el endpoint no lo tenga que validar."""
    assert ordered([LOAD, CHUNK, EMBED]) == [CHUNK, EMBED, LOAD]


def test_the_reset_goes_first():
    """Vaciar después de cargar dejaría la base vacía."""
    assert ordered([LOAD, RESET, CHUNK]) == [RESET, CHUNK, LOAD]


def test_a_repeated_step_runs_once():
    assert ordered([CHUNK, CHUNK]) == [CHUNK]


def test_an_unknown_step_is_dropped():
    """`ordered()` filtra contra la lista conocida, así que un paso inventado no
    llega al runner."""
    assert ordered([CHUNK, "compilar_el_kernel"]) == [CHUNK]


# --- Las guardas ---------------------------------------------------------------


class FakeSession:
    """Devuelve el job que se le diga como "ya corriendo", y traga el resto."""

    def __init__(self, running: IngestionJobRow | None = None, found=None) -> None:
        self._running = running
        self._found = found
        self.added: list = []

    async def execute(self, _statement):
        running = self._running

        class Result:
            def scalar_one_or_none(self):
                return running

            def scalars(self):
                return []

        return Result()

    async def get(self, _model, _key):
        return self._found

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        return None


def client_with(session: FakeSession) -> TestClient:
    async def override():
        yield session

    app.dependency_overrides[get_async_session] = override
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    """El trabajo no arranca de verdad en estos tests."""
    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.api.corpus.run_job", noop)


@pytest.fixture
def with_root(monkeypatch):
    """Una fuente local configurada y NINGUN bucket.

    Las dos cosas se fijan a proposito: dejar el `CORPUS_BUCKET` del `.env` sin
    tocar hace que el test dependa de la maquina donde corre, y este mismo test
    fallo cuando el `.env` real paso a tener bucket.

    || A local source configured and NO bucket. Both are pinned on purpose:
    leaving the `.env`'s `CORPUS_BUCKET` alone makes the test depend on the
    machine it runs on, and this very test failed once the real `.env` had one.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "CORPUS_ROOT", Path("D:/algun/corpus"))
    monkeypatch.setattr(settings, "CORPUS_BUCKET", "")
    return settings


def test_reset_without_confirmation_is_refused(with_root):
    """Un paso destructivo no viaja como booleano: un `reset=true` suelto en un
    historial de shell no debería vaciar una base."""
    response = client_with(FakeSession()).post("/corpus/rebuild", json={"reset": True})

    assert response.status_code == 400
    assert "confirm_tenant_id" in response.json()["detail"]


def test_reset_with_the_wrong_corpus_is_refused(with_root):
    response = client_with(FakeSession()).post(
        "/corpus/rebuild",
        json={
            "reset": True,
            "confirm_tenant_id": "otro_cliente",
            "confirm_doc_version": "otra_version",
        },
    )
    assert response.status_code == 400


def test_reset_with_the_right_corpus_is_accepted(with_root):
    settings = get_settings()
    response = client_with(FakeSession()).post(
        "/corpus/rebuild",
        json={
            "reset": True,
            "confirm_tenant_id": settings.TENANT_ID,
            "confirm_doc_version": settings.DOC_VERSION,
        },
    )

    assert response.status_code == 202
    assert response.json()["steps"][0] == RESET


def test_chunking_without_any_source_is_refused(monkeypatch):
    """Sin bucket Y sin directorio no hay nada que trocear."""
    monkeypatch.setattr(get_settings(), "CORPUS_ROOT", None)
    monkeypatch.setattr(get_settings(), "CORPUS_BUCKET", "")

    response = client_with(FakeSession()).post("/corpus/rebuild", json={"steps": [CHUNK]})

    assert response.status_code == 409
    assert "CORPUS_ROOT" in response.json()["detail"]


def test_chunking_with_only_a_bucket_is_allowed(monkeypatch):
    """Un bucket alcanza: el directorio local no hace falta."""
    monkeypatch.setattr(get_settings(), "CORPUS_ROOT", None)
    monkeypatch.setattr(get_settings(), "CORPUS_BUCKET", "un-bucket")

    response = client_with(FakeSession()).post("/corpus/rebuild", json={"steps": [CHUNK]})

    assert response.status_code == 202


def test_loading_without_a_configured_root_is_allowed(monkeypatch):
    """El caso más útil que hay: apuntar el servicio a una base nueva y cargarle
    el corpus que ya está en disco. Eso no necesita ningún documento fuente, así
    que exigir la raíz lo bloquearía."""
    monkeypatch.setattr(get_settings(), "CORPUS_ROOT", None)
    monkeypatch.setattr(get_settings(), "CORPUS_BUCKET", "")

    response = client_with(FakeSession()).post("/corpus/rebuild", json={"steps": [LOAD]})

    assert response.status_code == 202
    assert response.json()["steps"] == [LOAD]


def test_a_second_rebuild_is_refused_while_one_runs(with_root):
    """Dos rebuilds escribirían el mismo directorio y la misma tabla."""
    already = IngestionJobRow(id="el-que-corre", status=RUNNING, steps=[CHUNK])

    response = client_with(FakeSession(running=already)).post("/corpus/rebuild", json={})

    assert response.status_code == 409
    assert "el-que-corre" in response.json()["detail"]


def test_the_default_steps_are_the_whole_pipeline(with_root):
    response = client_with(FakeSession()).post("/corpus/rebuild", json={})
    assert response.json()["steps"] == [CHUNK, EMBED, LOAD]


def test_an_unknown_job_is_a_404():
    assert client_with(FakeSession(found=None)).get("/corpus/jobs/no-existe").status_code == 404
