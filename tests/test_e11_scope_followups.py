"""Commercial follow-ups keep their conversation scope without opening unrelated topics."""

from __future__ import annotations

import asyncio

from xeon.application.container import build_container
from xeon.config import Settings


def test_live_wording_after_pending_cement_choices_stays_commercial() -> None:
    async def check() -> None:
        container = build_container(Settings(_env_file=None, llm_provider="mock"))
        key = "e11-pending-cement"
        try:
            await container.agent.respond("cotice 10 bultos de cemento gris", conversation_key=key)
            assert container.conversation_memory.pending_candidates(key) is not None
            for index, message in enumerate(
                (
                    "el 1 el normal",
                    "bueno cotizame los 10 bultos del 1 el normal y el borrador",
                    "recojo sede norte mandame el total y el borrador",
                )
            ):
                response = await container.agent.respond(message, conversation_key=key)
                assert response.provider == "mock", message
                if index == 0:
                    assert container.conversation_memory.pending_candidates(key) is None
                    assert container.conversation_memory.last_sku(key) == "CEM-50"
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
            await container.agent.respond("Necesito una herramienta rara", conversation_key=key)
            response = await container.agent.respond("mandame el borrador", conversation_key=key)
            assert response.provider == "mock"
            unrelated = await container.agent.respond(
                "Dame noticias de politica y videojuegos", conversation_key=key
            )
            assert unrelated.provider == "local-policy"
        finally:
            await container.aclose()

    asyncio.run(check())
