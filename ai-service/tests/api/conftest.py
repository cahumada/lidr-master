"""Shared API test fixtures.

|| Fixtures compartidos de tests de API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


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

        def complete(self, *, system: str, user: str) -> str:
            return "respuesta"

    async def _runtime(session, settings, *, profile_id=None):
        return _StubLLM(), None

    for target in (
        "app.api.answer_agentic.synthesizer_runtime",
        "app.domain.graph.runner.synthesizer_runtime",
    ):
        monkeypatch.setattr(target, _runtime)
