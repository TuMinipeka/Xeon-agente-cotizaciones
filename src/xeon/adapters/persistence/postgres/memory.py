"""Persistent conversational context used by the guided executor."""

from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from xeon.adapters.conversation.memory import InMemoryConversationMemory, _Conversation
from xeon.adapters.persistence.postgres.schema import conversation_memories
from xeon.adapters.persistence.postgres.unit import PostgresUnit
from xeon.application.ports.conversation_memory import (
    PendingCandidates,
    PendingStockQuery,
    ProjectContext,
    ProposedLine,
)
from xeon.application.ports.llm import ChatMessage


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _decode(payload: dict[str, Any]) -> _Conversation:
    if payload.get("schema_version") != 1:
        raise ValueError("Version de memoria persistida no compatible.")
    data = payload["data"]
    pending = {
        key: PendingCandidates(
            skus=tuple(value["skus"]),
            names=tuple(value["names"]),
            quantity=_decimal(value["quantity"]),
            branch=value["branch"],
            attributes=tuple(value["attributes"]),
            question=value["question"],
            line_key=value["line_key"],
            stock_only=value["stock_only"],
        )
        for key, value in data["pending"].items()
    }
    stock_data = data["stock"]
    stock = (
        PendingStockQuery(
            branch_id=stock_data["branch_id"], quantity=_decimal(stock_data["quantity"])
        )
        if stock_data
        else None
    )
    project_data = data["project"]
    return _Conversation(
        messages=[ChatMessage(**item) for item in data["messages"]],
        sku=data["sku"],
        pending=pending,
        stock=stock,
        unverified_pc=data["unverified_pc"],
        proposal={key: Decimal(value) for key, value in data["proposal"].items()},
        project=ProjectContext(
            length_m=_decimal(project_data["length_m"]),
            width_m=_decimal(project_data["width_m"]),
            purpose=project_data["purpose"],
            whole_surface=project_data["whole_surface"],
        ),
    )


def _encode(conversation: _Conversation) -> dict[str, Any]:
    return {"schema_version": 1, "data": json.loads(json.dumps(asdict(conversation), default=str))}


class PostgresConversationMemory(InMemoryConversationMemory):
    """Reuse in-memory behavior while loading and writing each conversation in PostgreSQL."""

    def __init__(self, unit: PostgresUnit, *, max_turns: int, max_conversations: int) -> None:
        super().__init__(max_turns=max_turns, max_conversations=max_conversations)
        self._unit = unit

    def _read(self, key: str) -> None:
        with self._unit.connection() as connection:
            payload = connection.execute(
                select(conversation_memories.c.payload).where(
                    conversation_memories.c.conversation_key == self._unit.key(key)
                )
            ).scalar_one_or_none()
        if payload is None:
            self._conversations.pop(key, None)
        else:
            self._conversations[key] = _decode(payload)

    def _write(self, key: str) -> None:
        conversation = self._conversations.get(key)
        if conversation is None:
            return
        payload = _encode(conversation)
        statement = (
            insert(conversation_memories)
            .values(conversation_key=self._unit.key(key), payload=payload)
            .on_conflict_do_update(
                index_elements=[conversation_memories.c.conversation_key],
                set_={"payload": payload},
            )
        )
        with self._unit.connection() as connection:
            connection.execute(statement)

    def history(self, key: str) -> tuple[ChatMessage, ...]:
        self._read(key)
        return super().history(key)

    def last_sku(self, key: str) -> str | None:
        self._read(key)
        return super().last_sku(key)

    def pending_candidates(self, key: str) -> PendingCandidates | None:
        self._read(key)
        return super().pending_candidates(key)

    def all_pending_candidates(self, key: str) -> tuple[PendingCandidates, ...]:
        self._read(key)
        return super().all_pending_candidates(key)

    def pending_stock(self, key: str) -> PendingStockQuery | None:
        self._read(key)
        return super().pending_stock(key)

    def unverified_pc_context(self, key: str) -> bool:
        self._read(key)
        return super().unverified_pc_context(key)

    def project_data(self, key: str) -> ProjectContext:
        self._read(key)
        return super().project_data(key)

    def proposal_lines(self, key: str) -> tuple[ProposedLine, ...]:
        self._read(key)
        return super().proposal_lines(key)

    def set_pending_candidates(self, key: str, pending: PendingCandidates | None) -> None:
        self._read(key)
        super().set_pending_candidates(key, pending)
        self._write(key)

    def clear_pending_candidate(self, key: str, line_key: str) -> None:
        self._read(key)
        super().clear_pending_candidate(key, line_key)
        self._write(key)

    def set_pending_stock(self, key: str, request: PendingStockQuery | None) -> None:
        self._read(key)
        super().set_pending_stock(key, request)
        self._write(key)

    def set_unverified_pc_context(self, key: str, value: bool) -> None:
        self._read(key)
        super().set_unverified_pc_context(key, value)
        self._write(key)

    def remember_project_data(self, key: str, data: ProjectContext) -> None:
        self._read(key)
        super().remember_project_data(key, data)
        self._write(key)

    def remember_proposal(self, key: str, line: ProposedLine) -> None:
        self._read(key)
        super().remember_proposal(key, line)
        self._write(key)

    def clear_proposal(self, key: str) -> None:
        self._read(key)
        super().clear_proposal(key)
        self._write(key)

    def record(self, key: str, user: str, assistant: str, sku: str | None) -> None:
        self._read(key)
        super().record(key, user, assistant, sku)
        self._write(key)
