"""Capture what XEON actually sent to the LLM without changing its port."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


class RecordingLLM:
    def __init__(self, inner: LLMPort, on_call: Callable[[], None] | None = None) -> None:
        self.inner = inner
        self.on_call = on_call
        self.calls: list[tuple[ChatMessage, ...]] = []
        self.verified_contexts: list[str] = []
        self.token_estimate = 0

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    @property
    def model(self) -> str:
        return self.inner.model

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        if self.on_call is not None:
            self.on_call()
        frozen = tuple(messages)
        self.calls.append(frozen)
        # The current LLMPort has no usage field. This is explicitly an estimate.
        self.token_estimate += sum(max(1, len(message.content) // 4) for message in frozen)
        return await self.inner.complete(messages)

    def tool_contexts(self) -> list[str]:
        return self.verified_contexts + [
            message.content
            for call in self.calls
            for message in call
            if message.role == "system" and message.content.startswith("[XEON_TOOL:")
        ]

    def observe_verified_reply(self, reply: str) -> None:
        """Capture the new executor's mock-only tool markers for existing checks."""
        if "[XEON_TOOL:" in reply:
            self.verified_contexts.append(reply)

    async def aclose(self) -> None:
        await self.inner.aclose()
