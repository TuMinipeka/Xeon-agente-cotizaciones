from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from xeon.application.ports.llm import ChatMessage


@dataclass(frozen=True, slots=True)
class PendingCandidates:
    skus: tuple[str, ...]
    names: tuple[str, ...]
    quantity: Decimal | None
    branch: str


class ConversationMemory(Protocol):
    def history(self, key: str) -> tuple[ChatMessage, ...]: ...

    def last_sku(self, key: str) -> str | None: ...

    def pending_candidates(self, key: str) -> PendingCandidates | None: ...

    def set_pending_candidates(self, key: str, pending: PendingCandidates | None) -> None: ...

    def commercial_active(self, key: str) -> bool: ...

    def mark_commercial(self, key: str) -> None: ...

    def record(self, key: str, user: str, assistant: str, sku: str | None) -> None: ...
