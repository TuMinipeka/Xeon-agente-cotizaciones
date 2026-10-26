"""In-memory advisor inbox: the PostgreSQL adapter replaces it behind the same port."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from xeon.application.ports.advisor import (
    AdvisorEvent,
    AdvisorEventKind,
    AttentionStatus,
)

_LOG = logging.getLogger(__name__)


class InMemoryAdvisorInbox:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._events: dict[UUID, AdvisorEvent] = {}
        self._clock = clock or (lambda: datetime.now(UTC))

    def notify(
        self,
        *,
        tenant_id: str,
        event: AdvisorEventKind,
        conversation_key: str | None = None,
        quote_id: UUID | None = None,
    ) -> None:
        # Never log the conversation key: for WhatsApp it embeds the customer's phone number.
        _LOG.info("advisor_event tenant=%s event=%s", tenant_id, event)
        for existing in self._events.values():
            if (
                existing.status is AttentionStatus.PENDIENTE
                and existing.kind == event
                and existing.tenant_id == tenant_id
                and existing.conversation_key == conversation_key
                and existing.quote_id == quote_id
            ):
                return
        created = AdvisorEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            kind=event,
            created_at=self._clock(),
            conversation_key=conversation_key,
            quote_id=quote_id,
        )
        self._events[created.id] = created

    def get(self, event_id: UUID) -> AdvisorEvent | None:
        return self._events.get(event_id)

    def list_events(self, *, status: AttentionStatus | None = None) -> tuple[AdvisorEvent, ...]:
        found = [e for e in self._events.values() if status is None or e.status is status]
        return tuple(sorted(found, key=lambda item: item.created_at))

    def save(self, event: AdvisorEvent) -> AdvisorEvent:
        self._events[event.id] = event
        return event
