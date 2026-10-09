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


def test_stock_api_explains_partial_availability_without_reserving() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.get(
                "/v1/stock",
                params={
                    "sku": "CEM-50",
                    "requested_branch_id": "sede-norte",
                    "requested_quantity": "50",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["requested_quantity"] == "50"
            assert body["fulfillment_status"] == "partial"
            assert body["local_available"] == "20"
            assert body["shortfall"] == "30"
            assert all(item["kind"] != "local" for item in body["alternatives"])
            transfer = next(item for item in body["alternatives"] if item["kind"] == "transfer")
            assert transfer["origin_id"] == "sede-centro"
            assert transfer["quantity"] == "80"
            assert transfer["source"] == "synthetic-ferreteria-demo-xeon"
            assert transfer["observed_at"] == "2026-10-08T12:00:00+00:00"
            delivery = next(item for item in body["alternatives"] if item["kind"] == "delivery")
            assert delivery["origin_id"] == "origen-entrega-sintetica"
            assert delivery["quantity"] == "40"
            assert delivery["source"] == "synthetic-ferreteria-demo-xeon"

    asyncio.run(run())


def test_stock_api_keeps_unknown_when_local_snapshot_is_missing() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.get(
                "/v1/stock",
                params={
                    "sku": "TUB-PVC-20",
                    "requested_branch_id": "sede-centro",
                    "requested_quantity": "10",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["fulfillment_status"] == "unknown"
            assert body["fulfillment_status"] != "partial"
            assert body["local_available"] is None
            assert body["shortfall"] is None
            assert all(item["kind"] != "local" for item in body["items"])
            transfer = next(item for item in body["alternatives"] if item["kind"] == "transfer")
            assert transfer["origin_id"] == "sede-norte"
            assert transfer["quantity"] == "12"

    asyncio.run(run())


def test_stock_api_reports_sufficient_local_stock() -> None:
    async def run() -> None:
        async with _client() as client:
            response = await client.get(
                "/v1/stock",
                params={
                    "sku": "CEM-50",
                    "requested_branch_id": "sede-centro",
                    "requested_quantity": "50",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["fulfillment_status"] == "sufficient"
            assert body["local_available"] == "80"
            assert body["shortfall"] == "0"
            assert body["requested_quantity"] == "50"

    asyncio.run(run())
