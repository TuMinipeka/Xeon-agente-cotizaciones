"""Human follow-up boundary: events for advisors, without message contents."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

AdvisorEventKind = Literal["advisor_requested", "client_confirmed"]


class AttentionStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    ATENDIDO = "ATENDIDO"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


@dataclass(frozen=True, slots=True)
class AdvisorEvent:
    id: UUID
    tenant_id: str
    kind: AdvisorEventKind
    created_at: datetime
    status: AttentionStatus = AttentionStatus.PENDIENTE
    conversation_key: str | None = None
    quote_id: UUID | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    reason: str | None = None
    client_notified: bool | None = None


class AdvisorNotifier(Protocol):
    def notify(
        self,
        *,
        tenant_id: str,
        event: AdvisorEventKind,
        conversation_key: str | None = None,
        quote_id: UUID | None = None,
    ) -> None: ...


class AdvisorInbox(AdvisorNotifier, Protocol):
    """Notifier that also keeps the events so a human can attend them."""

    def get(self, event_id: UUID) -> AdvisorEvent | None: ...

    def list_events(self, *, status: AttentionStatus | None = None) -> tuple[AdvisorEvent, ...]: ...

    def save(self, event: AdvisorEvent) -> AdvisorEvent: ...

    def review_transaction(self, event_id: UUID) -> AbstractContextManager[None]:
        """Serialize an event and its quote while applying a human decision."""
        ...
