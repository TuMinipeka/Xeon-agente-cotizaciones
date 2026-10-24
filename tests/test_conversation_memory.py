from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx

from xeon.adapters.conversation.memory import InMemoryConversationMemory
from xeon.adapters.llm.openai_compatible import OpenAICompatibleLLM
from xeon.agent.toolbelt import _requests_discount
from xeon.api.app import create_app
from xeon.application.ports.conversation_memory import PendingCandidates, ResolvedLine
from xeon.config import Settings


def test_pending_candidates_are_bounded_and_cleared_after_selection() -> None:
    memory = InMemoryConversationMemory(max_turns=2, max_conversations=1)
    pending = PendingCandidates(("A", "B"), ("Alpha", "Beta"), Decimal(10), "sede-sur")
    memory.set_pending_candidates("first", pending)
    assert memory.pending_candidates("first") == pending
    memory.set_pending_candidates("first", None)
    assert memory.pending_candidates("first") is None
    memory.set_pending_candidates("first", pending)
    memory.record("second", "hola", "hola", None)
    assert memory.pending_candidates("first") is None


def test_resolved_lines_and_unresolved_quantity_are_conversation_local() -> None:
    memory = InMemoryConversationMemory(max_turns=2, max_conversations=2)
    memory.remember_unresolved_quantity("a", Decimal(5))
    memory.remember_lines("a", (ResolvedLine("CEM-50", Decimal(20)),))
    memory.remember_lines("a", (ResolvedLine("ALA-14", Decimal(100)),))
    memory.remember_lines("a", (ResolvedLine("CEM-50", Decimal(30)),))
    assert memory.resolved_lines("a") == (
        ResolvedLine("CEM-50", Decimal(30)),
        ResolvedLine("ALA-14", Decimal(100)),
    )
    assert memory.unresolved_quantity("a") == Decimal(5)
    assert memory.resolved_lines("b") == ()


def test_conversation_memory_keeps_only_last_six_turns_and_last_sku() -> None:
    memory = InMemoryConversationMemory(max_turns=6, max_conversations=3)
    for turn in range(8):
        memory.record("chat", f"user-{turn}", f"assistant-{turn}", "CEM-50" if turn == 2 else None)

    history = memory.history("chat")
    assert len(history) == 12
    assert [message.role for message in history] == ["user", "assistant"] * 6
    assert history[0].content == "user-2"
    assert history[-1].content == "assistant-7"
    assert memory.last_sku("chat") == "CEM-50"


def test_conversation_memory_evicts_least_recently_used_conversation() -> None:
    memory = InMemoryConversationMemory(max_turns=2, max_conversations=2)
    memory.record("a", "a", "A", "CEM-50")
    memory.record("b", "b", "B", "ALA-14")
    assert memory.history("a")
    memory.record("c", "c", "C", "TUB-PVC-20")

    assert memory.history("b") == ()
    assert memory.last_sku("b") is None
    assert memory.last_sku("a") == "CEM-50"
    assert memory.last_sku("c") == "TUB-PVC-20"


def test_discount_intent_recognizes_words_and_percentages() -> None:
    for message in (
        "Dame el descuento de siempre",
        "¿Hay alguna rebaja?",
        "Necesito un precio especial",
        "Aplica 12,5 % en 10 bultos de cemento",
    ):
        assert _requests_discount(message)
    assert not _requests_discount("Cotizame 10 bultos de cemento")


def test_grok_receives_history_between_system_context_and_current_turn() -> None:
    captured: list[list[dict[str, str]]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = request.read()
        import json

        messages = json.loads(payload)["messages"]
        captured.append(messages)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Respuesta"}}]})

    async def run() -> None:
        settings = Settings(llm_provider="grok", grok_api_key="test-only", _env_file=None)
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as provider_client:
            llm = OpenAICompatibleLLM(
                base_url=settings.grok_base_url,
                api_key="test-only",
                model=settings.grok_model,
                max_output_tokens=100,
                timeout_seconds=1,
                provider_name="grok",
                client=provider_client,
            )
            app = create_app(settings=settings, llm=llm)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                first = await client.post(
                    "/v1/chat",
                    json={
                        "conversation_id": "00000000-0000-0000-0000-000000000001",
                        "message": "Tienen tubo pvc de 1/2 pulgada?",
                    },
                )
                second = await client.post(
                    "/v1/chat",
                    json={
                        "conversation_id": "00000000-0000-0000-0000-000000000001",
                        "message": "Cotizame 5 unidades de ese mismo",
                    },
                )
            assert first.status_code == second.status_code == 200

    asyncio.run(run())
    roles = [message["role"] for message in captured[1]]
    assert roles == ["system", "system", "user", "assistant", "user"]
    assert captured[1][-3]["content"] == "Tienen tubo pvc de 1/2 pulgada?"
    assert captured[1][-1]["content"] == "Cotizame 5 unidades de ese mismo"
    assert "SKU=TUB-PVC-20" in captured[1][1]["content"]
