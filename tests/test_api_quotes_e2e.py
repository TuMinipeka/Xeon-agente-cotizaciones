from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.config import Settings


@asynccontextmanager
async def _client(
    catalog: InMemoryProductCatalog | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(llm_provider="mock", _env_file=None)
    container = build_container(settings, catalog=catalog)
    transport = httpx.ASGITransport(app=create_app(container=container))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield client


def test_create_and_get_synthetic_draft() -> None:
    async def run() -> None:
        async with _client() as client:
            created = await client.post(
                "/v1/quotes",
                json={
                    "tenant_id": "demo",
                    "request_id": "t01-req",
                    "lines": [
                        {"query": "CEM-50", "quantity": "50"},
                        {"query": "ALA-14", "quantity": "300"},
                    ],
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert body["outcome"] == "draft_ready"
            quote = body["quote"]
            assert quote["status"] == "DRAFT"
            assert quote["version"] == 1
            assert quote["total"] == "2000000.00"
            fetched = await client.get(
                f"/v1/quotes/{quote['id']}",
                params={"tenant_id": "demo"},
            )
            assert fetched.status_code == 200
            assert fetched.json()["id"] == quote["id"]
            assert fetched.json()["total"] == "2000000.00"

    asyncio.run(run())


def test_idempotent_retry_does_not_create_second_draft() -> None:
    async def run() -> None:
        payload = {
            "tenant_id": "demo",
            "request_id": "same-key",
            "lines": [{"query": "CEM-50", "quantity": "2"}],
        }
        async with _client() as client:
            first = await client.post("/v1/quotes", json=payload)
            second = await client.post("/v1/quotes", json=payload)
            assert first.status_code == 201
            assert second.status_code == 200
            assert second.json()["quote"]["replayed"] is True
            assert second.json()["quote"]["id"] == first.json()["quote"]["id"]

    asyncio.run(run())


def test_ambiguous_product_asks_for_clarification() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.post(
                "/v1/quotes",
                json={
                    "tenant_id": "demo",
                    "request_id": "t02",
                    "lines": [{"query": "el coso del aire", "quantity": "1"}],
                },
            )
            assert response.status_code == 422
            body = response.json()
            assert body["outcome"] == "clarification_required"
            assert body["reason"] == "ambiguous_reference"

    asyncio.run(run())


def test_measurements_without_units_ask_for_clarification() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.post(
                "/v1/quotes",
                json={
                    "tenant_id": "demo",
                    "request_id": "t03",
                    "lines": [{"query": "La pieza mide 20 x 30 x 10", "quantity": "1"}],
                },
            )
            assert response.status_code == 422
            assert response.json()["reason"] == "missing_units"

    asyncio.run(run())


def test_unavailable_catalog_is_not_sold_out() -> None:
    async def run() -> None:
        catalog = InMemoryProductCatalog()
        catalog.mark_unavailable()
        async with _client(catalog) as client:
            response = await client.post(
                "/v1/quotes",
                json={
                    "tenant_id": "demo",
                    "request_id": "t06",
                    "lines": [{"query": "CEM-50", "quantity": "1"}],
                },
            )
            assert response.status_code == 503
            body = response.json()
            assert body["outcome"] == "catalog_unavailable"
            assert "no se puede confirmar existencia" in body["message"].casefold()

    asyncio.run(run())


def test_discount_request_does_not_invent_policy() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.post(
                "/v1/quotes",
                json={
                    "tenant_id": "demo",
                    "request_id": "t08",
                    "discount_requested": True,
                    "lines": [{"query": "CEM-50", "quantity": "1"}],
                },
            )
            assert response.status_code == 422
            assert response.json()["outcome"] == "discount_policy_unavailable"

    asyncio.run(run())


def test_quote_flow_keeps_mock_provider() -> None:
    async def run() -> None:
        async with _client() as client:
            health = await client.get("/health")
            chat = await client.post("/v1/chat", json={"message": "hola"})
            assert health.json()["provider"] == "mock"
            assert chat.json()["provider"] == "mock"
            assert "sensitive" not in chat.text

    asyncio.run(run())
