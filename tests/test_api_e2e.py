import asyncio

import httpx

from xeon.api.app import create_app
from xeon.config import Settings


def test_mock_chat_runs_end_to_end_without_external_calls() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/v1/chat", json={"message": "hola"})

    response = asyncio.run(run())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["model"] == "mock-xeon-v1"
    assert "soy XEON" in payload["reply"]


def test_chat_runs_three_tools_and_creates_synthetic_draft() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/chat",
                json={"message": "necesito 50 bultos de cemento"},
            )

    response = asyncio.run(run())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert payload["outcome"] == "draft_ready"
    assert payload["tools_used"] == ["find_product", "consult_stock", "create_draft"]
    assert payload["quote_id"] is not None
    assert "CEM-50" in payload["reply"]
    assert "DRAFT" in payload["reply"]
    assert "1445000.00" in payload["reply"]


def test_health_does_not_expose_secrets() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", reto_key="sensitive-value", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(run())

    assert response.status_code == 200
    assert "sensitive-value" not in response.text
