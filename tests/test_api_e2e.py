import asyncio
from uuid import UUID

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
    assert payload["provider"] == "local-policy"
    assert payload["model"] == "commercial-scope-v1"
    assert "material o herramienta" in payload["reply"]


def test_health_does_not_expose_secrets() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", groq_api_key="sensitive-value", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(run())

    assert response.status_code == 200
    assert "sensitive-value" not in response.text


def test_chat_asks_location_then_keeps_candidates_until_natural_selection() -> None:
    async def run() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        conversation_id = UUID("11111111-1111-1111-1111-111111111111")
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            location = await client.post(
                "/v1/chat",
                json={
                    "conversation_id": str(conversation_id),
                    "message": "necesito 10 laminas de zinc para una casa",
                },
            )
            candidates = await client.post(
                "/v1/chat",
                json={"conversation_id": str(conversation_id), "message": "zona centro"},
            )
            selected = await client.post(
                "/v1/chat",
                json={
                    "conversation_id": str(conversation_id),
                    "message": "La primera opcion",
                },
            )
        return location, candidates, selected

    location, candidates, selected = asyncio.run(run())

    assert "ciudad o zona" in location.json()["reply"]
    candidate_reply = candidates.json()["reply"]
    assert "Lamina de zinc calibre 28" in candidate_reply
    assert "LAM-ZIN" not in candidate_reply
    assert "SKU" not in candidate_reply
    assert "create_quote_draft" not in candidate_reply

    selected_reply = selected.json()["reply"]
    assert "10 laminas" in selected_reply
    assert "borrador" not in selected_reply.casefold()
    assert "LAM-ZIN" not in selected_reply
    assert "SKU" not in selected_reply
