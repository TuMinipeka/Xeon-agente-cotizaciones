from __future__ import annotations

from collections.abc import Sequence

from xeon.application.ports.llm import ChatMessage, LLMResponse


class MockLLM:
    """Deterministic provider used by CI and zero-cost local development."""

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        user_text = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        if "hola" in user_text.casefold():
            text = (
                "Hola, soy XEON. Esta base usa datos sinteticos y todavia no consulta precios ni "
                "inventario. Puedo ayudarte a precisar los productos de una futura cotizacion."
            )
        else:
            text = (
                "Entendi tu solicitud. Esta base aun no tiene conectadas las herramientas "
                "comerciales, por lo que no inventare referencias, precios ni disponibilidad."
            )
        return LLMResponse(text=text, provider="mock", model="mock-xeon-v1")

    async def aclose(self) -> None:
        return None
