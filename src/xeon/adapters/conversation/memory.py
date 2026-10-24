from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from xeon.application.ports.conversation_memory import PendingCandidates
from xeon.application.ports.llm import ChatMessage


@dataclass(slots=True)
class _Conversation:
    messages: list[ChatMessage] = field(default_factory=list)
    sku: str | None = None
    pending: PendingCandidates | None = None
    commercial_active: bool = False


class InMemoryConversationMemory:
    """Bounded process-local history; oldest conversations are evicted first."""

    def __init__(self, *, max_turns: int = 6, max_conversations: int = 1000) -> None:
        if max_turns < 1 or max_conversations < 1:
            raise ValueError("Conversation memory limits must be positive.")
        self._max_turns = max_turns
        self._max_conversations = max_conversations
        self._conversations: OrderedDict[str, _Conversation] = OrderedDict()

    def history(self, key: str) -> tuple[ChatMessage, ...]:
        conversation = self._conversations.get(key)
        if conversation is None:
            return ()
        self._conversations.move_to_end(key)
        return tuple(conversation.messages)

    def last_sku(self, key: str) -> str | None:
        conversation = self._conversations.get(key)
        if conversation is None:
            return None
        self._conversations.move_to_end(key)
        return conversation.sku

    def pending_candidates(self, key: str) -> PendingCandidates | None:
        conversation = self._conversations.get(key)
        if conversation is None:
            return None
        self._conversations.move_to_end(key)
        return conversation.pending

    def set_pending_candidates(self, key: str, pending: PendingCandidates | None) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        self._conversations.move_to_end(key)
        conversation.pending = pending
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)

    def commercial_active(self, key: str) -> bool:
        conversation = self._conversations.get(key)
        if conversation is None:
            return False
        self._conversations.move_to_end(key)
        return conversation.commercial_active

    def mark_commercial(self, key: str) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        self._conversations.move_to_end(key)
        conversation.commercial_active = True
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)

    def record(self, key: str, user: str, assistant: str, sku: str | None) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        self._conversations.move_to_end(key)
        conversation.messages.extend(
            (
                ChatMessage(role="user", content=user),
                ChatMessage(role="assistant", content=assistant),
            )
        )
        del conversation.messages[: -2 * self._max_turns]
        if sku is not None:
            conversation.sku = sku
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)
