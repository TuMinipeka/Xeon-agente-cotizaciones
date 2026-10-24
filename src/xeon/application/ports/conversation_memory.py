from __future__ import annotations

from typing import Protocol

from xeon.application.ports.llm import ChatMessage


class ConversationMemory(Protocol):
    def history(self, key: str) -> tuple[ChatMessage, ...]: ...

    def last_sku(self, key: str) -> str | None: ...

    def record(self, key: str, user: str, assistant: str, sku: str | None) -> None: ...
