"""Regressions from agy's live S16-S20 transcript, without paid calls."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from tests.guided_steps import add_product, select_pickup
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.ports.llm import ChatMessage, LLMResponse
from xeon.config import Settings


class ScriptedLLM:
    provider_name = "scripted-local"
    model = "scripted-local-v1"

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        system = messages[0].content
        user = messages[-1].content
        if "Redacta una orientacion" in system:
            text = (
                "### **Orientación preliminar**\n**Partidas preliminares**\n"
                "- Piso para ganado\n¿Se trabajará toda esa superficie o solo una parte?"
            )
        elif "mejor dejala en 15" in user:
            text = '{"intents":[{"kind":"agregar","product":"cemento","quantity":15}]}'
        elif "no es 35 son 15" in user:
            text = '{"intents":[{"kind":"agregar","quantity":35}]}'
        elif "quiero 20 bultos cemento gris y 3 palas" in user:
            text = '{"intents":[{"kind":"agregar","product":"pala","quantity":20}]}'
        elif "estan disponibles esos 10 bultos en sede norte" in user:
            text = (
                '{"intents":[{"kind":"consultar_stock","product":"cemento",'
                '"quantity":10,"branch":"sede-norte"}]}'
            )
        elif "tienen o no tornillos m3 para pc" in user:
            text = '{"intents":[{"kind":"consultar_producto","product":"tornillos"}]}'
        else:
            text = "fallback determinista"
        return LLMResponse(text=text, provider=self.provider_name, model=self.model)

    async def aclose(self) -> None:
        return None


def test_s16_absolute_correction_overrides_model_addition() -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        try:
            await add_product(container, "s16", "cemento", "CEM-50", 20)
            await container.agent.respond_reply(
                "y si compro 50 hay descuento?", conversation_key="s16"
            )
            await container.agent.respond_reply(
                "mejor dejala en 15 bultos de cemento", conversation_key="s16"
            )
            reply = await container.agent.respond_reply(
                "no es 35 son 15 nomas", conversation_key="s16"
            )
            cart = container.carts.get("s16")
            assert cart is not None
            assert [(line.sku, line.quantity) for line in cart.confirmed_lines()] == [
                ("CEM-50", Decimal(15))
            ]
            assert "TOTAL confirmado: $433.500" in reply.text
            assert "$1.011.500" not in reply.text
        finally:
            await container.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "command",
    [
        "mejor dejala en 15 bultos de cemento",
        "dejámelo en 15 bultos de cemento",
        "ponle 15 bultos de cemento",
        "cambialo a 15 bultos de cemento",
        "solo 15 bultos de cemento",
        "nomas en 15 bultos de cemento",
    ],
)
def test_s16_absolute_phrasings_never_add_to_existing_sku(command: str) -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        try:
            await add_product(container, "set", "cemento", "CEM-50", 20)
            await container.agent.respond_reply(command, conversation_key="set")
            cart = container.carts.get("set")
            assert cart is not None
            assert cart.confirmed_lines()[0].quantity == Decimal(15)
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s16_plain_add_without_additive_verb_sets_quantity() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            await add_product(container, "add", "cemento", "CEM-50", 20)
            await container.agent.respond_reply("15 bultos de cemento", conversation_key="add")
            cart = container.carts.get("add")
            assert cart is not None
            assert cart.confirmed_lines()[0].quantity == Decimal(15)
            await container.agent.respond_reply(
                "agrega otros 5 bultos de cemento", conversation_key="add"
            )
            cart = container.carts.get("add")
            assert cart is not None
            assert cart.confirmed_lines()[0].quantity == Decimal(20)
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s17_pending_variant_keeps_its_own_quantity_and_cement() -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        try:
            await add_product(container, "s17", "cemento", "CEM-50", 20)
            await container.agent.respond_reply("pon 15 bultos de cemento", conversation_key="s17")
            await add_product(container, "s17", "pala", "PAL-RED-FIB", 2)
            reply = await container.agent.respond_reply(
                "Quita una pala, deja solo una.", conversation_key="s17"
            )
            cart = container.carts.get("s17")
            assert cart is not None
            assert [(line.sku, line.quantity) for line in cart.confirmed_lines()] == [
                ("CEM-50", Decimal(15)),
                ("PAL-RED-FIB", Decimal(1)),
            ]
            assert len(cart.lines) == 2
            assert "TOTAL confirmado: $477.200" in reply.text
            assert "pendiente de elegir referencia" not in reply.text
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s18_stock_product_branch_same_turn_or_one_clarification() -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        try:
            first = await container.agent.respond_reply(
                "estan disponibles esos 10 bultos en sede norte", conversation_key="s18"
            )
            assert first.step == "inicio"
            assert any(option.id == "start:products" for option in first.options)
            await add_product(container, "s18", "cemento", "CEM-50", 10)
            payment = await select_pickup(container, "s18", "sede-norte")
            assert payment.step == "pago"
            summary = await container.agent.respond_reply("payment:0", conversation_key="s18")
            assert "TOTAL confirmado: $289.000" in summary.text
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s19_plain_text_and_whole_surface_confirmation() -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        try:
            first = await container.agent.respond_reply(
                "tengo un corral de 20x30m y piso concreto", conversation_key="s19"
            )
            assert first.step == "proyecto"
            second = await container.agent.respond_reply(
                "toda la superficie 20x30 dame lista materiales corral ganado "
                "no preguntes mas medidas",
                conversation_key="s19",
            )
            assert "Toda la superficie confirmada" in second.text
            assert "¿Se trabajará toda la superficie" not in second.text
            assert "preliminar" in second.text
            assert "**" not in first.text + second.text
            assert "###" not in first.text + second.text
            project = container.conversation_memory.project_data("s19")
            assert project.area_m2 == Decimal(600)
            assert project.whole_surface is True
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s19_chat_api_uses_same_plain_text_boundary() -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(container=container)),
            base_url="http://127.0.0.1",
        )
        try:
            response = await client.post(
                "/v1/chat",
                json={"message": "corral para ganado de 20x30 m", "conversation_id": str(uuid4())},
            )
            assert response.status_code == 200
            reply = response.json()["reply"]
            assert "preliminar" in reply.casefold()
            assert "**" not in reply and "###" not in reply
        finally:
            await client.aclose()
            await container.aclose()

    asyncio.run(run())


def test_s20_pc_compatibility_persists_across_rephrasing() -> None:
    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", _env_file=None), llm=ScriptedLLM()
        )
        try:
            for message in (
                "hola tienen tornillos para motherboard de pc",
                "tienen m3 o 6-32 para placa base",
                "tienen o no tornillos m3 para pc",
                "tienen tornillos 6-32",
            ):
                reply = await container.agent.respond(message, conversation_key="s20")
                assert "compatibilidad verificada" in reply.text
                assert "Tornillo galvanizado" not in reply.text
            assert container.conversation_memory.unverified_pc_context("s20") is True
        finally:
            await container.aclose()

    asyncio.run(run())
