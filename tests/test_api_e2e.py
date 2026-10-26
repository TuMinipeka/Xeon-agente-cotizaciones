import asyncio

import httpx

from xeon.api.app import app, create_app
from xeon.config import Settings


def test_imported_app_uses_mock_during_tests() -> None:
    async def run() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            chat = await client.post("/v1/chat", json={"message": "hola"})
            return health, chat

    health, chat = asyncio.run(run())

    assert health.status_code == 200
    assert chat.status_code == 200
    assert health.json()["provider"] == "mock"
    assert health.json()["model"] == "mock-xeon-v1"
    assert chat.json()["provider"] == "local-guided"
    assert chat.json()["model"] == "guided-funnel-v1"
    assert chat.json()["step"] == "inicio"
    assert {option["id"] for option in chat.json()["options"]} >= {"start:products"}


def test_mock_chat_runs_end_to_end_without_external_calls() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/v1/chat", json={"message": "hola"})

    response = asyncio.run(run())

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local-guided"
    assert payload["model"] == "guided-funnel-v1"
    assert payload["step"] == "inicio"
    assert "Cotizar productos" in payload["reply"]


def test_health_does_not_expose_secrets() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", groq_api_key="sensitive-value", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(run())

    assert response.status_code == 200
    assert "sensitive-value" not in response.text
