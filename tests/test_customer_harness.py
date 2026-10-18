import asyncio
from collections.abc import Sequence

import httpx

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.catalog.synthetic_seed import CORE_SYNTHETIC_PRODUCTS
from xeon.agent.customer_safety import CustomerResponsePolicy
from xeon.api.app import create_app
from xeon.application.ports.llm import ChatMessage, LLMResponse
from xeon.config import Settings


class SpyLLM:
    def __init__(self, response: str = "respuesta segura") -> None:
        self.calls = 0
        self.response = response

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=self.response, provider="spy", model="spy-v1")

    async def aclose(self) -> None:
        return None


def test_out_of_scope_request_is_blocked_before_llm() -> None:
    async def run() -> tuple[httpx.Response, SpyLLM]:
        llm = SpyLLM("Te recomiendo CEM-50 en https://example.com")
        app = create_app(settings=Settings(_env_file=None), llm=llm)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat",
                json={"message": "Busca tarjetas graficas y dame enlaces para comprarlas"},
            )
        return response, llm

    response, llm = asyncio.run(run())

    assert response.status_code == 200
    assert llm.calls == 0
    reply = response.json()["reply"]
    assert "ferreter" in reply.casefold()
    assert "http" not in reply
    assert "CEM-50" not in reply


def test_customer_output_falls_back_when_llm_leaks_code_or_unapproved_link() -> None:
    async def run() -> tuple[httpx.Response, SpyLLM]:
        llm = SpyLLM("Compra el SKU CEM-50 en https://example.com")
        app = create_app(settings=Settings(_env_file=None), llm=llm)
        transport = httpx.ASGITransport(app=app)
        conversation_id = "44444444-4444-4444-4444-444444444444"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/v1/chat",
                json={"conversation_id": conversation_id, "message": "necesito cemento"},
            )
            response = await client.post(
                "/v1/chat",
                json={"conversation_id": conversation_id, "message": "zona centro"},
            )
        assert "ciudad o zona" in first.json()["reply"]
        return response, llm

    response, llm = asyncio.run(run())

    assert response.status_code == 200
    assert llm.calls == 2
    reply = response.json()["reply"]
    assert "Cemento gris 50 kg" in reply
    assert "CEM-50" not in reply
    assert "SKU" not in reply
    assert "http" not in reply
    assert "HERMES" not in reply


def test_only_registered_links_are_allowed_by_output_policy() -> None:
    policy = CustomerResponsePolicy(approved_links=("https://ferreteria.example/catalogo",))

    approved = policy.sanitize(
        "Puedes verlo en https://ferreteria.example/catalogo",
        fallback="respuesta segura",
    )
    rejected = policy.sanitize(
        "Puedes verlo en https://otro.example/producto",
        fallback="respuesta segura",
    )

    assert approved.endswith("https://ferreteria.example/catalogo")
    assert rejected == "respuesta segura"


def test_mixed_request_keeps_commercial_part_and_asks_location() -> None:
    async def run() -> httpx.Response:
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/chat",
                json={"message": "Necesito cemento y busca tarjetas graficas con enlaces"},
            )

    response = asyncio.run(run())

    reply = response.json()["reply"]
    assert "no manejo informaci" in reply.casefold()
    assert "ciudad o zona" in reply
    assert "http" not in reply


def test_missing_hardware_product_keeps_cart_without_promising_escalation() -> None:
    async def run() -> httpx.Response:
        catalog = InMemoryProductCatalog(products=CORE_SYNTHETIC_PRODUCTS)
        app = create_app(
            settings=Settings(llm_provider="mock", _env_file=None),
            catalog=catalog,
        )
        transport = httpx.ASGITransport(app=app)
        conversation_id = "22222222-2222-2222-2222-222222222222"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/v1/chat",
                json={"conversation_id": conversation_id, "message": "2 bultos de cemento"},
            )
            await client.post(
                "/v1/chat",
                json={"conversation_id": conversation_id, "message": "zona centro"},
            )
            return await client.post(
                "/v1/chat",
                json={"conversation_id": conversation_id, "message": "necesito clavos"},
            )

    response = asyncio.run(run())

    reply = response.json()["reply"]
    assert "no encuentro" in reply.casefold()
    assert "Cemento gris 50 kg" in reply
    assert "agotado" not in reply.casefold()
    assert "avis" not in reply.casefold()
    assert "encargado" not in reply.casefold()
