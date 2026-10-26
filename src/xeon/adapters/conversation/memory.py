from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal

from xeon.application.ports.conversation_memory import (
    PendingCandidates,
    PendingStockQuery,
    ProjectContext,
    ProposedLine,
)
from xeon.application.ports.llm import ChatMessage


@dataclass(slots=True)
class _Conversation:
    messages: list[ChatMessage] = field(default_factory=list)
    sku: str | None = None
    pending: dict[str, PendingCandidates] = field(default_factory=dict)
    stock: PendingStockQuery | None = None
    unverified_pc: bool = False
    proposal: dict[str, Decimal] = field(default_factory=dict)
    project: ProjectContext = field(default_factory=ProjectContext)


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
        return next(reversed(conversation.pending.values()), None)

    def set_pending_candidates(self, key: str, pending: PendingCandidates | None) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        self._conversations.move_to_end(key)
        if pending is None:
            conversation.pending.clear()
        else:
            conversation.pending[pending.line_key or "default"] = pending
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)

    def all_pending_candidates(self, key: str) -> tuple[PendingCandidates, ...]:
        conversation = self._conversations.get(key)
        return tuple(conversation.pending.values()) if conversation is not None else ()

    def clear_pending_candidate(self, key: str, line_key: str) -> None:
        conversation = self._conversations.get(key)
        if conversation is not None:
            conversation.pending.pop(line_key or "default", None)

    def pending_stock(self, key: str) -> PendingStockQuery | None:
        conversation = self._conversations.get(key)
        return conversation.stock if conversation is not None else None

    def set_pending_stock(self, key: str, request: PendingStockQuery | None) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        conversation.stock = request

    def unverified_pc_context(self, key: str) -> bool:
        conversation = self._conversations.get(key)
        return bool(conversation and conversation.unverified_pc)

    def set_unverified_pc_context(self, key: str, value: bool) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        conversation.unverified_pc = value

    def project_data(self, key: str) -> ProjectContext:
        conversation = self._conversations.get(key)
        if conversation is None:
            return ProjectContext()
        self._conversations.move_to_end(key)
        return conversation.project

    def remember_project_data(self, key: str, data: ProjectContext) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        self._conversations.move_to_end(key)
        previous = conversation.project
        conversation.project = ProjectContext(
            length_m=data.length_m if data.length_m is not None else previous.length_m,
            width_m=data.width_m if data.width_m is not None else previous.width_m,
            purpose=data.purpose or previous.purpose,
            whole_surface=(
                data.whole_surface if data.whole_surface is not None else previous.whole_surface
            ),
        )
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)

    def proposal_lines(self, key: str) -> tuple[ProposedLine, ...]:
        conversation = self._conversations.get(key)
        if conversation is None:
            return ()
        self._conversations.move_to_end(key)
        return tuple(ProposedLine(sku, qty) for sku, qty in conversation.proposal.items())

    def remember_proposal(self, key: str, line: ProposedLine) -> None:
        conversation = self._conversations.setdefault(key, _Conversation())
        self._conversations.move_to_end(key)
        conversation.proposal[line.sku] = line.quantity
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)

    def clear_proposal(self, key: str) -> None:
        conversation = self._conversations.get(key)
        if conversation is not None:
            conversation.proposal.clear()

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
