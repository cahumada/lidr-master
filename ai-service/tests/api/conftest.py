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
