"""Deterministic regressions for the commercial conversation QA report."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal

from xeon.application.container import build_container
from xeon.application.ports.llm import ChatMessage, LLMResponse
from xeon.config import Settings


def test_cart_revision_and_attribute_choice_preserve_verified_total() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            replies = [
                (await container.agent.respond(message, conversation_key="qa-cart")).text
                for message in (
                    "cemento x20",
                    "cambialo a 15 y deja dos palas",
                    "quita una",
                    "redonda con mango de fibra",
                    "cuanto llevo producto por producto",
                )
            ]
            assert "$433.500" in replies[-1]
            assert "$43.700" in replies[-1]
            assert "TOTAL confirmado: $477.200" in replies[-1]
            assert all("fuera de alcance" not in text.casefold() for text in replies)
            cart = container.carts.get("qa-cart")
            assert cart is not None and cart.quote_version == 3
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
            await container.agent.respond("10 bultos de cemento", conversation_key="one-call")
            assert llm.calls == 1
            cart = container.carts.get("one-call")
            assert cart is not None and cart.confirmed_lines()[0].quantity == Decimal(10)
        finally:
            await container.aclose()

    asyncio.run(run())


def test_stock_and_policy_followups_preserve_quote() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            replies = [
                (await container.agent.respond(message, conversation_key="qa-policy")).text
                for message in (
                    "10 bultos",
                    "disponibles en sede Norte?",
                    "que opciones tengo para pagar y recoger?",
                    "resumeme mi cotizacion",
                )
            ]
            assert "sede-norte" in replies[1]
            assert "Pagos: Efectivo, Transferencia, Tarjeta" in replies[2]
            assert "Recogida: Mismo día si hay stock" in replies[2]
            assert "TOTAL confirmado: $289.000" in replies[3]
            assert all("fuera de alcance" not in text.casefold() for text in replies)
        finally:
            await container.aclose()

    asyncio.run(run())


def test_hypothetical_and_project_data_do_not_change_cart() -> None:
    async def run() -> None:
        container = build_container(Settings(llm_provider="mock", _env_file=None))
        try:
            await container.agent.respond("10 bultos", conversation_key="qa-project")
            before = container.carts.get("qa-project")
            assert before is not None
            await container.agent.respond(
                "que descuento por 50 bultos?", conversation_key="qa-project"
            )
            advice = await container.agent.respond(
                "Tengo un corral para ganado de 20 x 30 m", conversation_key="qa-project"
            )
            stock = await container.agent.respond(
                "hay disponibilidad?", conversation_key="qa-project"
            )
            after = container.carts.get("qa-project")
            assert after == before
            assert container.conversation_memory.project_data("qa-project").area_m2 == Decimal(600)
            assert "validación técnica" in advice.text
            assert "¿En qué sede" in stock.text
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
            assert "peso por bulto" in result.text.casefold()
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
