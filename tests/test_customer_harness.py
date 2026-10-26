from __future__ import annotations

import asyncio
from collections.abc import Sequence

import httpx

from xeon.api.app import create_app
from xeon.application.ports.llm import ChatMessage, LLMResponse
from xeon.config import Settings


class SpyLLM:
    def __init__(self, response: str = "respuesta segura") -> None:
        self.calls: list[tuple[ChatMessage, ...]] = []
        self.response = response

    @property
    def provider_name(self) -> str:
        return "spy"

    @property
    def model(self) -> str:
        return "spy-v1"

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        self.calls.append(tuple(messages))
        return LLMResponse(text=self.response, provider=self.provider_name, model=self.model)

    async def aclose(self) -> None:
        return None


def test_out_of_scope_request_is_blocked_before_llm() -> None:
    async def run() -> tuple[httpx.Response, SpyLLM]:
        llm = SpyLLM("Te recomiendo CEM-50 en https://example.com")
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None), llm=llm)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat",
                json={"message": "Busca tarjetas graficas y dame enlaces para comprarlas"},
            )
        return response, llm

    response, llm = asyncio.run(run())
    assert response.status_code == 200
    assert llm.calls == []
    assert response.json()["provider"] == "local-guided"
    assert "cotización" in response.json()["reply"].casefold()
    assert "http" not in response.json()["reply"]


def test_invalid_interpreter_output_uses_verified_local_response() -> None:
    async def run() -> httpx.Response:
        llm = SpyLLM("Compra el SKU CEM-50 en https://example.com")
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None), llm=llm)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/v1/chat",
                json={
                    "message": "necesito cemento",
                    "conversation_id": "00000000-0000-0000-0000-000000000123",
                },
            )
            return await client.post(
                "/v1/chat",
                json={
                    "message": "start:products",
                    "conversation_id": "00000000-0000-0000-0000-000000000123",
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "producto" in reply.casefold()
    assert "CEM-50" not in reply
    assert "http" not in reply
    assert "SKU" not in reply


def test_untrusted_model_link_never_reaches_guided_reply() -> None:
    async def run() -> str:
        llm = SpyLLM('{"choice":"no_encaja"} https://otro.example/producto')
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None), llm=llm)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/v1/chat", json={"message": "continuar"})
        return str(response.json()["reply"])

    reply = asyncio.run(run())
    assert "https://otro.example" not in reply
    assert "Cotizar productos" in reply


def test_mixed_request_executes_commercial_part_without_rejection_prefix() -> None:
    async def run() -> tuple[httpx.Response, SpyLLM]:
        llm = SpyLLM("Puedo ayudarte con cemento.")
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None), llm=llm)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat",
                json={"message": "Necesito cemento y busca tarjetas graficas con enlaces"},
            )
        return response, llm

    response, llm = asyncio.run(run())
    assert response.status_code == 200
    assert len(llm.calls) <= 1
    assert "no manejo informaci" not in response.json()["reply"].casefold()
    assert "Cotizar productos" in response.json()["reply"]
    assert "tarjetas graficas" not in response.json()["reply"].casefold()
