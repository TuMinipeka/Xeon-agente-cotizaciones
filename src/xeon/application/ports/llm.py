from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class LLMPort(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse: ...

    async def aclose(self) -> None: ...
