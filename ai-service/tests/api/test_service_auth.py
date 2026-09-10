"""Service authentication: the shared token, and what stays open.

|| Autenticación del servicio: el token compartido, y qué queda abierto.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import require_service_token

TOKEN = "s3cr3t-token"


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _app(monkeypatch, token: str) -> FastAPI:
    """The same shape as `app/main.py`: guarded routers, `/health` outside.

    || La misma forma que `app/main.py`: routers con guarda, `/health` afuera.
    """
    monkeypatch.setenv("SERVICE_TOKEN", token)
    get_settings.cache_clear()

    router = APIRouter(prefix="/guarded")

    @router.get("")
    def read() -> dict:
        return {"ok": True}

    @router.post("")
    def write() -> dict:
        return {"ok": True}

    test_app = FastAPI()
    test_app.include_router(router, dependencies=[Depends(require_service_token)])

    @test_app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return test_app


def test_without_a_configured_token_everything_answers(monkeypatch):
    """The mode the tests and the evals run in, unchanged.

    || El modo en que corren los tests y los evals, sin cambios.
    """
    with TestClient(_app(monkeypatch, "")) as client:
        assert client.get("/guarded").status_code == 200
        assert client.post("/guarded").status_code == 200
        assert client.get("/health").status_code == 200


def test_a_configured_token_closes_reads_too(monkeypatch):
    """A read is not free: `GET /search` calls the embedder on every query.

    || Una lectura no es gratis: `GET /search` llama al embedder en cada
    consulta.
    """
    with TestClient(_app(monkeypatch, TOKEN)) as client:
        assert client.get("/guarded").status_code == 401
        assert client.post("/guarded").status_code == 401


def test_the_right_token_gets_through(monkeypatch):
    with TestClient(_app(monkeypatch, TOKEN)) as client:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        assert client.get("/guarded", headers=headers).status_code == 200
        assert client.post("/guarded", headers=headers).status_code == 200


def test_a_missing_and_a_wrong_token_are_indistinguishable(monkeypatch):
    """That difference only helps somebody trying tokens.

    || Esa diferencia solo le sirve a quien está probando tokens.
    """
    with TestClient(_app(monkeypatch, TOKEN)) as client:
        missing = client.get("/guarded")
        wrong = client.get("/guarded", headers={"Authorization": "Bearer nope"})

    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()
    assert missing.headers["www-authenticate"] == "Bearer"


def test_health_stays_open(monkeypatch):
    """Closing it would make the platform restart the service in a loop.

    || Cerrarlo haría que la plataforma reinicie el servicio en loop.
    """
    with TestClient(_app(monkeypatch, TOKEN)) as client:
        assert client.get("/health").status_code == 200


def test_an_endpoint_added_later_is_closed_by_default(monkeypatch):
    """The reason the guard lives on the router and not on each endpoint.

    || La razón por la que la guarda vive en el router y no en cada endpoint.
    """
    monkeypatch.setenv("SERVICE_TOKEN", TOKEN)
    get_settings.cache_clear()

    router = APIRouter(prefix="/guarded")

    @router.get("")
    def read() -> dict:
        return {"ok": True}

    test_app = FastAPI()
    test_app.include_router(router, dependencies=[Depends(require_service_token)])

    # Un endpoint agregado DESPUÉS, sin ninguna anotación propia.
    @router.delete("/{item}")
    def destroy(item: str) -> dict:
        return {"deleted": item}

    test_app.include_router(router, dependencies=[Depends(require_service_token)])

    with TestClient(test_app) as client:
        assert client.delete("/guarded/x").status_code == 401


def test_production_without_a_token_does_not_boot(monkeypatch):
    """Open with the look of closed is worse than the declared absence of auth.

    || Abierto con aspecto de cerrado es peor que la ausencia declarada de auth.
    """
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SERVICE_TOKEN", "")

    with pytest.raises(ValueError) as raised:
        Settings(_env_file=None)

    assert "SERVICE_TOKEN" in str(raised.value)


def test_production_with_a_token_boots(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SERVICE_TOKEN", TOKEN)

    assert Settings(_env_file=None).SERVICE_TOKEN == TOKEN
