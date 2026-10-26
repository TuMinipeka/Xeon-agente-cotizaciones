from __future__ import annotations

from collections.abc import Sequence

from xeon.application.ports.llm import ChatMessage, LLMResponse, TokenUsage

_MOCK_PROVIDER_NAME = "mock"
_MOCK_MODEL = "mock-xeon-v1"


class MockLLM:
    """Deterministic provider used by CI and zero-cost local development."""

    @property
    def provider_name(self) -> str:
        return _MOCK_PROVIDER_NAME

    @property
    def model(self) -> str:
        return _MOCK_MODEL

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        user_text = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        tool_context = next(
            (
                message.content
                for message in reversed(messages)
                if message.role == "system" and message.content.startswith("[XEON_TOOL:")
            ),
            None,
        )
        customer_draft = next(
            (
                message.content.removeprefix("[XEON_CUSTOMER_DRAFT]\n")
                for message in reversed(messages)
                if message.role == "system"
                and message.content.startswith("[XEON_CUSTOMER_DRAFT]\n")
            ),
            None,
        )
        if customer_draft is not None:
            text = customer_draft
        elif "hola" in user_text.casefold():
            text = (
                "Hola, soy XEON. Esta base usa datos sinteticos y herramientas comerciales "
                "para identificar productos por busqueda hibrida (RAG + base de datos) "
                "sin inventar precios ni disponibilidad."
            )
        elif tool_context is not None:
            text = f"Entendi tu solicitud. Resultado verificado por XEON:\n{tool_context}"
        else:
            text = (
                "Entendi tu solicitud. No se identifico una referencia en el catalogo; "
                "por lo que no inventare referencias, precios ni disponibilidad."
            )
        # The mock consumes no tokens: zero is a fact here, not an estimate.
        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=self.model,
            usage=TokenUsage(0, 0),
        )

    async def aclose(self) -> None:
        return None
