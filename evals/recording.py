"""Capture what XEON actually sent to the LLM without changing its port."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


def format_tool_event(event: str) -> str:
    """Format a tool trace event into a verified tool context string."""
    tokens = event.strip().split()
    if len(tokens) < 2 or tokens[0] != "TOOL":
        return event
    name = tokens[1]
    pairs: dict[str, str] = {}
    for token in tokens[2:]:
        if "=" in token:
            key, val = token.split("=", 1)
            pairs[key] = val
    if name == "get_stock_by_branches":
        sku = pairs.get("sku", "")
        sede = pairs.get("sede", "")
        disponible = pairs.get("disponible", "unknown")
        vigencia = pairs.get("vigencia", "unknown")
        header = (
            f"[XEON_TOOL:get_stock_by_branches sku={sku} sede_solicitada={sede} "
            f"disponible_local={disponible} vigencia={vigencia}]"
        )
        return f"{header}\n- SKU={sku} sede_solicitada={sede}"
    if name == "search_products":
        status = pairs.get("status", "")
        sku = pairs.get("sku", "")
        return f"[XEON_TOOL:search_products status={status}]\n- SKU={sku}"
    if name == "create_quote_draft":
        status = pairs.get("status", "DRAFT")
        quote_id = pairs.get("quote_id", "")
        return f"[XEON_TOOL:create_quote_draft status={status} quote_id={quote_id}]"
    return event


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

    def observe_tool_event(self, event: str) -> None:
        """Capture tool trace events (from xeon.tools logger) for both live and offline modes."""
        formatted = format_tool_event(event)
        if formatted not in self.verified_contexts:
            self.verified_contexts.append(formatted)

    async def aclose(self) -> None:
        await self.inner.aclose()
