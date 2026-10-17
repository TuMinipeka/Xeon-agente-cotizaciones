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


def test_chat_keeps_pending_candidates_until_customer_confirms_sku() -> None:
    async def run() -> tuple[httpx.Response, httpx.Response]:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        conversation_id = UUID("11111111-1111-1111-1111-111111111111")
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            candidate_response = await client.post(
                "/v1/chat",
                json={
                    "conversation_id": str(conversation_id),
                    "message": "necesito 50 bultos para fundir una placa y pegar ladrillo",
                },
            )
            confirmation_response = await client.post(
                "/v1/chat",
                json={
                    "conversation_id": str(conversation_id),
                    "message": "La primera opción",
                },
            )
        return candidate_response, confirmation_response

    candidate_response, confirmation_response = asyncio.run(run())

    assert candidate_response.status_code == 200
    candidate_reply = candidate_response.json()["reply"]
    assert "Cemento gris 50 kg" in candidate_reply
    assert "CEM-50" not in candidate_reply
    assert "SKU" not in candidate_reply
    assert "get_stock_by_branches" not in candidate_reply
    assert "create_quote_draft" not in candidate_reply

    assert confirmation_response.status_code == 200
    confirmation_reply = confirmation_response.json()["reply"]
    assert "Preparé un borrador" in confirmation_reply
    assert "50 bultos" in confirmation_reply
    assert "CEM-50" not in confirmation_reply
    assert "SKU" not in confirmation_reply
    assert "confirmed_selection" not in confirmation_reply
