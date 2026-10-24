from __future__ import annotations

import asyncio
from collections.abc import Sequence

import httpx

from xeon.agent.customer_safety import CustomerResponsePolicy
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
    assert response.json()["provider"] == "local-policy"
    assert "ferreter" in response.json()["reply"].casefold()
    assert "http" not in response.json()["reply"]


def test_customer_output_falls_back_when_llm_leaks_code_or_unapproved_link() -> None:
    async def run() -> httpx.Response:
        llm = SpyLLM("Compra el SKU CEM-50 en https://example.com")
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None), llm=llm)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/v1/chat", json={"message": "necesito cemento"})

    response = asyncio.run(run())
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "producto y la cantidad" in reply
    assert "CEM-50" not in reply
    assert "http" not in reply
    assert "SKU" not in reply


def test_only_registered_links_are_allowed_by_output_policy() -> None:
    policy = CustomerResponsePolicy(approved_links=("https://ferreteria.example/catalogo",))
    approved = policy.sanitize(
        "Puedes verlo en https://ferreteria.example/catalogo", fallback="respuesta segura"
    )
    rejected = policy.sanitize(
        "Puedes verlo en https://otro.example/producto", fallback="respuesta segura"
    )
    assert approved.endswith("https://ferreteria.example/catalogo")
    assert rejected == "respuesta segura"


def test_mixed_request_sends_only_commercial_part_to_llm() -> None:
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
    assert len(llm.calls) == 1
    assert llm.calls[0][-1].content == "Necesito cemento"
    assert "no manejo informaci" in response.json()["reply"].casefold()
    assert "Puedo ayudarte con cemento." in response.json()["reply"]
