"""Deterministic regressions for the commercial conversation QA report."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal

from tests.guided_steps import add_product, select_pickup
from xeon.application.container import build_container
from xeon.application.ports.llm import ChatMessage, LLMResponse
from xeon.config import Settings


def test_cart_revision_and_attribute_choice_preserve_verified_total() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            await add_product(container, "qa-cart", "cemento", "CEM-50", 20)
            await container.agent.respond_reply(
                "cambialo a 15 bultos de cemento", conversation_key="qa-cart"
            )
            await add_product(container, "qa-cart", "pala", "PAL-RED-FIB", 2)
            reply = await container.agent.respond_reply(
                "quita una pala", conversation_key="qa-cart"
            )
            assert "$433.500" in reply.text
            assert "$43.700" in reply.text
            assert "TOTAL confirmado: $477.200" in reply.text
            assert "fuera de alcance" not in reply.text.casefold()
            cart = container.carts.get("qa-cart")
            assert cart is not None and cart.quote_version == 4
            assert sum(
                (line.line_total.amount for line in cart.confirmed_lines()), Decimal(0)
            ) == Decimal("477200.00")
        finally:
            await container.aclose()

    asyncio.run(run())


def test_transactional_turn_uses_one_interpreter_call() -> None:
    class JsonLLM:
        calls = 0

        @property
        def provider_name(self) -> str:
            return "json-test"

        @property
        def model(self) -> str:
            return "json-test-v1"

        async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
            self.calls += 1
            return LLMResponse(
                text='{"intents":[{"kind":"agregar","product":"cemento","quantity":10}]}',
                provider=self.provider_name,
                model=self.model,
            )

        async def aclose(self) -> None:
            return None

    async def run() -> None:
        llm = JsonLLM()
        container = build_container(
            Settings(llm_provider="mock", _env_file=None),
            llm=llm,
        )
        try:
            await add_product(container, "one-call", "cemento", "CEM-50", 10)
            assert llm.calls == 0
            cart = container.carts.get("one-call")
            assert cart is not None and cart.confirmed_lines()[0].quantity == Decimal(10)
        finally:
            await container.aclose()

    asyncio.run(run())


def test_stock_and_policy_followups_preserve_quote() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            await add_product(container, "qa-policy", "cemento", "CEM-50", 10)
            payment = await select_pickup(container, "qa-policy", "sede-norte")
            assert payment.step == "pago"
            assert any(option.id == "payment:0" for option in payment.options)
            summary = await container.agent.respond_reply("payment:0", conversation_key="qa-policy")
            assert "sede-norte" in summary.text
            assert "TOTAL confirmado: $289.000" in summary.text
            assert "fuera de alcance" not in summary.text.casefold()
        finally:
            await container.aclose()

    asyncio.run(run())


def test_hypothetical_and_project_data_do_not_change_cart() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            await add_product(container, "qa-project", "cemento", "CEM-50", 10)
            before = container.carts.get("qa-project")
            assert before is not None
            await container.agent.respond_reply(
                "que descuento por 50 bultos?", conversation_key="qa-project"
            )
            advice = await container.agent.respond_reply(
                "Tengo un corral para ganado de 20 x 30 m", conversation_key="qa-project"
            )
            after = container.carts.get("qa-project")
            assert after == before
            assert container.conversation_memory.project_data("qa-project").area_m2 == Decimal(600)
            assert "validación técnica" in advice.text
            assert advice.step == "proyecto"
        finally:
            await container.aclose()

    asyncio.run(run())


def test_weight_and_delivery_questions_are_both_addressed() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            result = await container.agent.respond(
                "cuantos kilos contiene un bulto de arena o gravilla y si domicilio es gratis?",
                conversation_key="qa-multi",
            )
            assert "peso del bulto" in result.text.casefold()
            assert "domicilio:" in result.text.casefold()
            assert "pendiente de confirmar" in result.text.casefold()
        finally:
            await container.aclose()

    asyncio.run(run())


def test_motherboard_screws_need_verified_compatibility() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            for message in (
                "Hola, ¿tienen tornillos para motherboard?",
                "¿Esos tornillos sí sirven para fijar una placa base de computador?",
            ):
                result = await container.agent.respond(message, conversation_key="qa-screws")
                assert "compatibilidad verificada" in result.text
                assert "referencia sintetica" not in result.text.casefold()
            assert container.carts.get("qa-screws") is None
        finally:
            await container.aclose()

    asyncio.run(run())
