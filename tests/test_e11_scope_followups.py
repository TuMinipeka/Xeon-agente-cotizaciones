"""Commercial follow-ups keep their conversation scope without opening unrelated topics."""

from __future__ import annotations

import asyncio

from tests.guided_steps import add_product, select_pickup
from xeon.application.container import build_container
from xeon.config import Settings


def test_live_wording_after_pending_cement_choices_stays_commercial() -> None:
    async def check() -> None:
        container = build_container(Settings(_env_file=None, llm_provider="mock"))
        key = "e11-pending-cement"
        try:
            await add_product(container, key, "cemento", "CEM-50", 10)
            payment = await select_pickup(container, key, "sede-norte")
            assert payment.step == "pago"
            summary = await container.agent.respond_reply("payment:0", conversation_key=key)
            assert "TOTAL confirmado: $289.000" in summary.text
        finally:
            await container.aclose()

    asyncio.run(check())


def test_active_commercial_context_allows_free_followup_but_blocks_explicit_unrelated_topic() -> (
    None
):
    async def check() -> None:
        container = build_container(Settings(_env_file=None, llm_provider="mock"))
        key = "e11-commercial-active"
        try:
            await add_product(container, key, "cemento", "CEM-50", 10)
            response = await container.agent.respond_reply("more:view", conversation_key=key)
            assert response.step == "entrega"
            unrelated = await container.agent.respond_reply(
                "Dame noticias de politica y videojuegos", conversation_key=key
            )
            assert unrelated.step == "entrega"
            assert unrelated.text.startswith("Solo puedo ayudarte")
        finally:
            await container.aclose()

    asyncio.run(check())
