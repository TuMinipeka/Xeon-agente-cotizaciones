"""Conversation-local guided step state."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FunnelState:
    step: str = "inicio"
    selected_sku: str | None = None
    selected_line: str | None = None
    delivery: str | None = None
    branch_id: str | None = None
    address: str | None = None
    payment: str | None = None
    candidates: tuple[str, ...] = ()
    awaiting_number: bool = False
    awaiting_modification: bool = False


class FunnelRepository(Protocol):
    def get(self, conversation_key: str) -> FunnelState: ...

    def save(self, conversation_key: str, state: FunnelState) -> None: ...
