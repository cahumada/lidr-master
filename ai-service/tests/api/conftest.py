"""Shared API test fixtures.

|| Fixtures compartidos de tests de API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.config import get_settings
from app.domain.profiles import SynthesizerRuntime
from app.foundation.llm.wrapper import Completion


@pytest.fixture(autouse=True)
def unconfigured_service_token(monkeypatch):
    """Run the router tests with the service-token guard off, deliberately.

    `add-service-authentication` put a `require_service_token` dependency on
    every router, and it passes when `SERVICE_TOKEN` is empty. That made the
    suite depend on the developer's environment: with a token in the local
    `.env` — which is what a machine that has ever talked to the deployed
    service has — every test here gets 401 and asserts against an error body.
    52 of them failed that way, and CI could not see it, because CI defines no
    secrets and therefore always ran with the guard off.

    So the guard is turned off HERE, explicitly, instead of being off by
    accident. These tests assert endpoint contracts; the guard itself is
    covered by `test_service_auth.py`, which builds its own app and sets the
    token it needs — and does so after this fixture, so it still wins.

    || Corre los tests de router con el guard del token apagado, a propósito.
    `add-service-authentication` puso la dependencia en todos los routers, y
    pasa cuando `SERVICE_TOKEN` está vacío: eso volvió la suite dependiente
    del entorno de quien la corre. Con un token en el `.env` local —que es lo
    que tiene cualquier máquina que alguna vez le habló al servicio
    desplegado— cada test de acá recibe 401 y afirma contra un cuerpo de
    error. 52 fallaban así, y CI no lo veía porque no define secretos y
    entonces siempre corrió con el guard apagado. Ahora está apagado ACÁ, de
    forma explícita, en vez de estarlo por casualidad. El guard lo cubre
    `test_service_auth.py`, que arma su propia app y fija el token que
    necesita — después de este fixture, así que sigue ganando.
    """
    monkeypatch.setenv("SERVICE_TOKEN", "")
    get_settings.cache_clear()
    yield
    # The cache holds a Settings built from a patched environment; leaving it
    # there would hand the next test a token that no longer matches its env.
    # || El cache guarda un Settings armado con un entorno parcheado; dejarlo
    # le pasaría al test siguiente un token que ya no corresponde a su env.
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def skip_postgres_checkpointer(monkeypatch):
    """Avoid blocking TestClient startup on an unreachable Postgres.

    || Evita que el arranque de TestClient se cuelgue esperando Postgres.
    """

    @asynccontextmanager
    async def _unavailable():
        raise ConnectionError("Postgres checkpointer disabled in API tests")
        yield  # pragma: no cover — unreachable

    monkeypatch.setattr(
        "app.domain.graph.checkpointer.open_checkpointer",
        _unavailable,
    )


@pytest.fixture(autouse=True)
def stub_synthesizer_runtime(monkeypatch):
    """Keep the database and OpenAI out of the API tests.

    Every synthesis path resolves its LLM and persona through
    ``synthesizer_runtime``, which reads the ``answer_synthesizer`` profile
    and builds a client for whatever it says. These tests assert endpoint
    contracts, so both are stubbed at that one seam. A test that cares about
    the profile patches it again with what it needs.

    || Mantiene la base y OpenAI afuera de los tests de API. Cada camino de
    síntesis resuelve su LLM y su persona por ``synthesizer_runtime``. Un test
    que le importe el perfil lo vuelve a parchear con lo que necesita.
    """

    class _StubLLM:
        model = "stub-model"

        def complete(self, *, system: str, user: str) -> Completion:
            return Completion(text="respuesta")

    async def _runtime(session, settings, *, profile_id=None):
        return SynthesizerRuntime(
            llm=_StubLLM(), persona=None, guardrails=None, provider_id="openai"
        )

    for target in (
        "app.api.answer_agentic.synthesizer_runtime",
        "app.domain.graph.runner.synthesizer_runtime",
    ):
        monkeypatch.setattr(target, _runtime)


@pytest.fixture(autouse=True)
def skip_usage_ledger(monkeypatch):
    """API tests do not persist ledger rows. || Los tests de API no persisten asientos."""

    monkeypatch.setattr(
        "app.foundation.persistence.usage.UsageStore.record",
        lambda self, **kwargs: None,
    )
