"""The two `/business-db` endpoints, with the store stubbed at its seam.

Transport only: which run the listing marks as in force, where that came from,
and that each refusal gets its own status code. The store's rules — the
precedence, the partial index, the `loaded_data` guard — are tested against a
real Postgres in ``tests/domain/test_business_db_store.py``, which is where
they belong.

|| Los dos endpoints de `/business-db`, con el store stubbeado en su costura.
Solo transporte: qué corrida marca el listado como vigente, de dónde salió eso,
y que cada rechazo tenga su código. Las reglas del store —la precedencia, el
índice parcial, la guarda de `loaded_data`— se prueban contra un Postgres real
en ``tests/domain/test_business_db_store.py``, que es donde corresponden.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.domain.business_db_store import ActiveRun, MirrorRun, RunNotLoaded, TableBuild
from app.foundation.persistence.database import get_async_session
from app.main import app

LOADED = "20260909_214921"
NOT_LOADED = "20260909_174017"
DEV_RUN = "20260908_225731"


def _run(run_id: str, *, env: str = "PROD", loaded_data: bool = True) -> MirrorRun:
    return MirrorRun(
        tenant="life_seguros",
        env=env,
        run_id=run_id,
        extractor_version="1.0.0",
        created_at_utc=datetime(2026, 9, 9, tzinfo=UTC),
        status="complete" if loaded_data else "partial",
        loaded_metadata=True,
        loaded_dependencies=True,
        loaded_data=loaded_data,
        manifest_sha256="bc3ac04d19fb",
    )


# The three runs the mirror really holds, and only one has its data loaded.
# Copied from the deployment rather than invented, so the fixture cannot drift
# into a shape the extractor never produces.
# || Las tres corridas que el mirror tiene de verdad, y solo una con datos
# cargados. Copiadas del despliegue y no inventadas.
MIRROR = [
    _run(LOADED),
    _run(NOT_LOADED, loaded_data=False),
    _run(DEV_RUN, env="DEV", loaded_data=False),
]


class FakeStore:
    """Stands in for the store, recording what the router asked of it.

    || Reemplaza al store y registra qué le pidió el router.
    """

    def __init__(self) -> None:
        self.active = ActiveRun(run_id=LOADED, env="PROD", origin="default")
        self.runs = list(MIRROR)
        self.stamp = None
        self.activations: list[tuple[str, str | None]] = []
        # Only the active run has its edges built. That asymmetry is the point:
        # the listing has to make the other two distinguishable.
        # || Solo la corrida activa tiene aristas. Esa asimetría es el punto.
        self.builds: dict[tuple[str, str], TableBuild] = {
            ("PROD", LOADED): TableBuild(
                env="PROD",
                run_id=LOADED,
                edge_count=4873,
                code_count=460,
                doc_version="DW Funtionals 2026.1",
                built_at=datetime(2026, 9, 11, tzinfo=UTC),
            )
        }

    async def resolve(self, session, settings, tenant_id=None) -> ActiveRun:
        return self.active

    async def list_runs(self, session, tenant_id) -> list[MirrorRun]:
        return list(self.runs)

    async def find(self, session, tenant_id, run_id, env=None) -> MirrorRun | None:
        return next((run for run in self.runs if run.run_id == run_id), None)

    async def activate(self, session, *, tenant_id, run, activated_by=None):
        if not run.loaded_data:
            raise RunNotLoaded(f"loaded_data=false para {run.run_id!r}")
        self.activations.append((run.run_id, activated_by))
        self.active = ActiveRun(
            run_id=run.run_id,
            env=run.env,
            origin="selected",
            activated_at=datetime(2026, 9, 10, tzinfo=UTC),
            activated_by=activated_by,
        )
        return object()

    async def stamp_of(self, session, tenant_id, doc_version):
        return self.stamp

    async def table_builds(self, session, tenant_id):
        return dict(self.builds)


@pytest.fixture
def store(monkeypatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr("app.api.business_db.resolve_active_run", fake.resolve)
    monkeypatch.setattr("app.api.business_db.list_mirror_runs", fake.list_runs)
    monkeypatch.setattr("app.api.business_db.find_mirror_run", fake.find)
    monkeypatch.setattr("app.api.business_db.activate_run", fake.activate)
    monkeypatch.setattr("app.api.business_db.get_stamp", fake.stamp_of)
    monkeypatch.setattr("app.api.business_db.list_table_builds", fake.table_builds)
    return fake


@pytest.fixture
def client(store):
    class _NoSession:
        async def commit(self) -> None:
            return None

    async def no_session():
        yield _NoSession()

    app.dependency_overrides[get_async_session] = no_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_the_listing_marks_which_run_is_in_force_and_its_origin(client, store):
    body = client.get("/business-db/runs").json()

    assert body["active"]["run_id"] == LOADED
    assert body["active"]["origin"] == "default"
    active_flags = {run["run_id"]: run["is_active"] for run in body["runs"]}
    assert active_flags == {LOADED: True, NOT_LOADED: False, DEV_RUN: False}


def test_the_listing_says_which_runs_can_be_activated(client, store):
    """Las tres banderas viajan; solo `loaded_data` condiciona la activación."""
    body = client.get("/business-db/runs").json()
    by_run = {run["run_id"]: run for run in body["runs"]}

    assert by_run[LOADED]["can_activate"] is True
    assert by_run[NOT_LOADED]["can_activate"] is False
    # Las otras dos se informan igual, para que quien elige sepa qué cubre cada
    # corrida en vez de tener que adivinarlo del nombre.
    assert by_run[NOT_LOADED]["loaded_metadata"] is True
    assert by_run[NOT_LOADED]["loaded_dependencies"] is True
    assert by_run[LOADED]["manifest_sha256"] == "bc3ac04d19fb"


def test_a_run_the_mirror_does_not_have_is_404(client, store):
    """Aceptarla guardaría una selección apuntando a nada."""
    response = client.post("/business-db/runs/no_existe/activate")

    assert response.status_code == 404
    assert "no_existe" in response.json()["detail"]
    assert store.activations == []


def test_a_run_without_loaded_data_is_409_and_not_a_silent_accept(client, store):
    response = client.post(f"/business-db/runs/{NOT_LOADED}/activate")

    assert response.status_code == 409
    assert "loaded_data" in response.json()["detail"]
    assert store.activations == []
    # Y la selección anterior no se movió.
    assert client.get("/business-db/runs").json()["active"]["run_id"] == LOADED


def test_activating_with_a_configured_default_works_and_flips_the_origin(client, store):
    """Un valor en `BUSINESS_DB_RUN_ID` NO es un candado: es el default.

    El `409` por «fijada por el despliegue» no existe — era la variante
    override, y esta decisión es de operación del producto.
    """
    assert store.active.origin == "default"

    response = client.post(
        f"/business-db/runs/{LOADED}/activate", json={"activated_by": "cristian"}
    )

    assert response.status_code == 200
    assert response.json()["active"]["origin"] == "selected"
    assert response.json()["active"]["activated_by"] == "cristian"
    assert store.activations == [(LOADED, "cristian")]


def test_activating_without_a_body_declares_no_author(client, store):
    response = client.post(f"/business-db/runs/{LOADED}/activate")

    assert response.status_code == 200
    assert response.json()["active"]["activated_by"] is None
    assert store.activations == [(LOADED, None)]


def test_a_blank_author_is_absent_and_not_an_empty_string(client, store):
    """No se inventa un autor, y tampoco se guarda uno vacío como si fuera uno."""
    client.post(f"/business-db/runs/{LOADED}/activate", json={"activated_by": "   "})

    assert store.activations == [(LOADED, None)]


def test_with_no_run_at_all_the_listing_says_why(client, store):
    store.active = ActiveRun(
        run_id=None, env="PROD", origin="none", reason="no hay corrida ni default"
    )

    body = client.get("/business-db/runs").json()

    assert body["active"]["run_id"] is None
    assert body["active"]["origin"] == "none"
    assert body["active"]["reason"] == "no hay corrida ni default"
    # Y ninguna corrida se marca vigente por descarte.
    assert all(run["is_active"] is False for run in body["runs"])


def test_the_stamp_travels_with_the_listing_and_flags_the_drift(client, store):
    """El desfasaje se muestra, no se deduce."""

    class _Stamp:
        run_id = NOT_LOADED
        env = "PROD"
        doc_version = "DW Funtionals 2026.1"
        stamped_at = datetime(2026, 9, 9, tzinfo=UTC)
        rows_updated = 56537

    store.stamp = _Stamp()

    body = client.get("/business-db/runs").json()

    assert body["stamp"]["run_id"] == NOT_LOADED
    assert body["stamp"]["rows_updated"] == 56537
    # Estampado con una, activa otra: la consola puede decir "estampado con X ·
    # activa Y" sin una segunda llamada.
    assert body["stamp"]["matches_active"] is False


def test_a_stamp_from_the_active_run_reports_no_drift(client, store):
    class _Stamp:
        run_id = LOADED
        env = "PROD"
        doc_version = "DW Funtionals 2026.1"
        stamped_at = datetime(2026, 9, 9, tzinfo=UTC)
        rows_updated = 56537

    store.stamp = _Stamp()

    assert client.get("/business-db/runs").json()["stamp"]["matches_active"] is True


def test_no_stamp_at_all_is_absent_rather_than_false(client, store):
    """Nunca estampado y estampado-con-otra son cosas distintas."""
    body = client.get("/business-db/runs").json()

    assert body["stamp"] is None


def test_the_listing_says_which_runs_have_their_table_edges_built(client, store):
    # Activating a run whose batch never ran leaves the block with no tables,
    # and nothing else would say why.
    # || Activar una corrida sin batch deja el bloque sin tablas, y nada más lo
    # diría.
    body = client.get("/business-db/runs").json()

    built = {run["run_id"]: run["tables_built"] for run in body["runs"]}
    assert built == {LOADED: True, NOT_LOADED: False, DEV_RUN: False}


def test_a_built_run_reports_what_the_batch_produced(client, store):
    body = client.get("/business-db/runs").json()
    row = next(run for run in body["runs"] if run["run_id"] == LOADED)

    assert row["table_edge_count"] == 4873
    assert row["tables_built_at"] is not None


def test_an_unbuilt_run_reports_zero_without_claiming_a_build(client, store):
    body = client.get("/business-db/runs").json()
    row = next(run for run in body["runs"] if run["run_id"] == NOT_LOADED)

    assert row["tables_built"] is False
    assert row["table_edge_count"] == 0
    assert row["tables_built_at"] is None


def test_a_build_with_no_edges_is_still_a_build(client, store):
    # Zero edges from a batch that ran is a fact about the run; zero because the
    # batch never ran is a deployment gap. The flag is the row, not the count.
    # || Cero aristas de un batch que corrió es un hecho; cero porque nunca
    # corrió es un hueco de despliegue.
    store.builds[("PROD", NOT_LOADED)] = TableBuild(
        env="PROD",
        run_id=NOT_LOADED,
        edge_count=0,
        code_count=0,
        doc_version="DW Funtionals 2026.1",
        built_at=datetime(2026, 9, 11, tzinfo=UTC),
    )

    body = client.get("/business-db/runs").json()
    row = next(run for run in body["runs"] if run["run_id"] == NOT_LOADED)

    assert row["tables_built"] is True
    assert row["table_edge_count"] == 0


@pytest.fixture
def dictionary(monkeypatch):
    """The reader stubbed at its seam; the SQL is tested against Postgres.

    || El reader stubbeado en su costura; el SQL se prueba contra Postgres.
    """
    from app.generation.rag.business_db.models import (
        DictionaryColumn,
        DictionaryForeignKey,
        TableDictionaryDetail,
    )

    known = {
        "CLAIM_NPR": TableDictionaryDetail(
            table_name="CLAIM_NPR",
            description_es="Cesiones de siniestro no proporcional",
            columns=[
                DictionaryColumn(
                    name="NCLAIM",
                    description="Número que identifica al siniestro.",
                    data_type="NUMBER",
                    nullable=False,
                    is_primary_key=True,
                ),
                DictionaryColumn(name="NNUMBER", is_primary_key=True, is_foreign_key=True),
            ],
            primary_key=["NCLAIM", "NNUMBER"],
            foreign_keys=[
                DictionaryForeignKey(
                    name="REF_CONTRNPRO",
                    columns=["NNUMBER"],
                    references_table="CONTRNPRO",
                )
            ],
            run_id=LOADED,
            env="PROD",
        )
    }

    def _read(database_url, tenant, env, run_id, table_name, schema="visualtime"):
        return known.get(table_name)

    monkeypatch.setattr("app.api.business_db.read_table_dictionary_full", _read)
    return known


def test_the_dictionary_carries_columns_keys_and_marks(client, dictionary):
    body = client.get("/business-db/tables/CLAIM_NPR").json()

    assert body["description_es"] == "Cesiones de siniestro no proporcional"
    assert body["primary_key"] == ["NCLAIM", "NNUMBER"]
    assert body["foreign_keys"][0]["references_table"] == "CONTRNPRO"
    marks = {c["name"]: (c["is_primary_key"], c["is_foreign_key"]) for c in body["columns"]}
    assert marks["NCLAIM"] == (True, False)
    assert marks["NNUMBER"] == (True, True)


def test_a_table_the_run_does_not_have_is_a_404(client, dictionary):
    response = client.get("/business-db/tables/NO_EXISTE")

    assert response.status_code == 404
    assert "NO_EXISTE" in response.json()["detail"]


def test_without_an_active_run_the_dictionary_is_a_409(client, store, dictionary):
    """The dictionary only lives in the mirror: no run, no fallback.

    || El diccionario solo vive en el mirror: sin corrida, sin caída.
    """
    store.active = ActiveRun(run_id=None, env="PROD", origin="none", reason="nadie eligió")

    response = client.get("/business-db/tables/CLAIM_NPR")

    assert response.status_code == 409
