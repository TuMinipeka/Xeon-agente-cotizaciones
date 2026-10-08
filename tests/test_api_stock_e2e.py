from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.config import Settings


@asynccontextmanager
async def _client() -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(llm_provider="mock", _env_file=None)
    container = build_container(settings)
    transport = httpx.ASGITransport(app=create_app(container=container))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield client


def test_alternative_branch_is_not_reported_as_local_via_api() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.get(
                "/v1/stock",
                params={"sku": "TUB-PVC-20", "requested_branch_id": "sede-centro"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["sku"] == "TUB-PVC-20"
            assert body["requested_branch_id"] == "sede-centro"
            assert body["items"]
            assert all(item["kind"] != "local" for item in body["items"])
            transfer = next(item for item in body["items"] if item["kind"] == "transfer")
            assert transfer["origin_id"] == "sede-norte"
            assert transfer["source"] == "synthetic-ferreteria-demo-xeon"

    asyncio.run(run())


def test_stock_api_keeps_origin_and_availability_kind() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.get(
                "/v1/stock",
                params={"sku": "CEM-50", "requested_branch_id": "sede-centro"},
            )
            assert response.status_code == 200
            items = response.json()["items"]
            kinds = {item["kind"] for item in items}
            assert kinds == {"local", "transfer", "delivery"}
            local = next(item for item in items if item["kind"] == "local")
            assert local["origin_id"] == "sede-centro"
            transfer = next(item for item in items if item["kind"] == "transfer")
            assert transfer["origin_id"] == "sede-norte"
            delivery = next(item for item in items if item["kind"] == "delivery")
            assert delivery["origin_id"] == "origen-entrega-sintetica"
            assert delivery["branch_id"] is None

    asyncio.run(run())
