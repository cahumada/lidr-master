"""GET /usage/summary with the store mocked.

|| GET /usage/summary con el store mockeado.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.foundation.persistence.database import get_async_session
from app.foundation.persistence.usage import UsageByModel, UsageTotals
from app.main import app


class FakeUsageStore:
    def __init__(self) -> None:
        self.totals = UsageTotals(
            total_calls=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            by_model=[],
        )
        self.calls: list[dict] = []

    async def summarize(self, tenant_id: str, **kwargs) -> UsageTotals:
        self.calls.append({"tenant_id": tenant_id, **kwargs})
        return self.totals


@pytest.fixture
def store(monkeypatch) -> FakeUsageStore:
    fake = FakeUsageStore()
    monkeypatch.setattr("app.api.usage._store", lambda session: fake)
    return fake


@pytest.fixture
def client(store):
    async def no_session():
        yield None

    app.dependency_overrides[get_async_session] = no_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_an_empty_ledger_returns_zeros(client, store):
    body = client.get("/usage/summary").json()

    assert body["total_calls"] == 0
    assert body["input_tokens"] == 0
    assert body["output_tokens"] == 0
    assert body["total_tokens"] == 0
    assert body["by_model"] == []
    assert store.calls[0]["tenant_id"]


def test_summary_mirrors_the_store_totals(client, store):
    store.totals = UsageTotals(
        total_calls=2,
        input_tokens=200,
        output_tokens=80,
        total_tokens=280,
        by_model=[
            UsageByModel(
                provider_id="openai",
                model="gpt-4o-mini",
                calls=2,
                input_tokens=200,
                output_tokens=80,
                total_tokens=280,
            )
        ],
    )

    body = client.get("/usage/summary").json()

    assert body["total_calls"] == 2
    assert body["input_tokens"] == 200
    assert body["output_tokens"] == 80
    assert body["total_tokens"] == 280
    assert body["by_model"] == [
        {
            "provider_id": "openai",
            "model": "gpt-4o-mini",
            "calls": 2,
            "input_tokens": 200,
            "output_tokens": 80,
            "total_tokens": 280,
        }
    ]


def test_from_later_than_to_is_422(client):
    response = client.get(
        "/usage/summary",
        params={"from": "2026-09-07T12:00:00Z", "to": "2026-09-01T12:00:00Z"},
    )

    assert response.status_code == 422
    assert "from" in response.json()["detail"]
