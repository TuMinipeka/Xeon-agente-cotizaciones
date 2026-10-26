"""In-memory advisor inbox: the PostgreSQL adapter replaces it behind the same port."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from xeon.application.ports.advisor import (
    AdvisorEvent,
    AdvisorEventKind,
    AttentionStatus,
)

_LOG = logging.getLogger(__name__)


class InMemoryAdvisorInbox:
    def __init__(
        self, *, clock: Callable[[], datetime] | None = None, max_events: int = 2_000
    ) -> None:
        self._max_events = max_events
        self._events: dict[UUID, AdvisorEvent] = {}
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = RLock()

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
        self._trim()

    def _trim(self) -> None:
        """Bound memory: drop resolved events first, then the oldest advisor requests."""
        for victims in (
            lambda e: e.status is not AttentionStatus.PENDIENTE,
            lambda e: e.kind == "advisor_requested",
            lambda e: True,
        ):
            while len(self._events) > self._max_events:
                candidate = next((e for e in self.list_events() if victims(e)), None)
                if candidate is None:
                    break
                del self._events[candidate.id]

    def get(self, event_id: UUID) -> AdvisorEvent | None:
        return self._events.get(event_id)

    def list_events(self, *, status: AttentionStatus | None = None) -> tuple[AdvisorEvent, ...]:
        found = [e for e in self._events.values() if status is None or e.status is status]
        return tuple(sorted(found, key=lambda item: item.created_at))

    def save(self, event: AdvisorEvent) -> AdvisorEvent:
        self._events[event.id] = event
        return event

    @contextmanager
    def review_transaction(self, event_id: UUID) -> Iterator[None]:
        del event_id
        with self._lock:
            yield
