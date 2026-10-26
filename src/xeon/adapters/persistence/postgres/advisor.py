"""Tenant-scoped PostgreSQL advisor inbox and atomic human review boundary."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from xeon.adapters.persistence.postgres.schema import advisor_events, quote_drafts
from xeon.adapters.persistence.postgres.unit import PostgresUnit
from xeon.application.ports.advisor import (
    AdvisorEvent,
    AdvisorEventKind,
    AttentionStatus,
)

_LOG = logging.getLogger(__name__)


def _decode(row: Any) -> AdvisorEvent:
    return AdvisorEvent(
        id=UUID(row.id),
        tenant_id=row.tenant_id,
        kind=cast(AdvisorEventKind, row.kind),
        created_at=row.created_at,
        status=AttentionStatus(row.status),
        conversation_key=row.conversation_key,
        quote_id=UUID(row.quote_id) if row.quote_id else None,
        resolved_by=row.resolved_by,
        resolved_at=row.resolved_at,
        reason=row.reason,
        client_notified=row.client_notified,
    )


class PostgresAdvisorInbox:
    def __init__(self, unit: PostgresUnit, tenant_id: str) -> None:
        self._unit = unit
        self._tenant_id = tenant_id

    def notify(
        self,
        *,
        tenant_id: str,
        event: AdvisorEventKind,
        conversation_key: str | None = None,
        quote_id: UUID | None = None,
    ) -> None:
        if tenant_id != self._tenant_id:
            raise ValueError("Tenant de evento de asesor invalido.")
        _LOG.info("advisor_event tenant=%s event=%s", tenant_id, event)
        with self._unit.connection() as connection:
            connection.execute(
                insert(advisor_events)
                .values(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    kind=event,
                    created_at=datetime.now(UTC),
                    status=AttentionStatus.PENDIENTE.value,
                    conversation_key=conversation_key,
                    quote_id=str(quote_id) if quote_id else None,
                )
                .on_conflict_do_nothing()
            )

    def get(self, event_id: UUID) -> AdvisorEvent | None:
        with self._unit.connection() as connection:
            row = connection.execute(
                select(advisor_events).where(
                    advisor_events.c.id == str(event_id),
                    advisor_events.c.tenant_id == self._tenant_id,
                )
            ).one_or_none()
        return _decode(row) if row is not None else None

    def list_events(self, *, status: AttentionStatus | None = None) -> tuple[AdvisorEvent, ...]:
        statement = select(advisor_events).where(advisor_events.c.tenant_id == self._tenant_id)
        if status is not None:
            statement = statement.where(advisor_events.c.status == status.value)
        statement = statement.order_by(advisor_events.c.created_at, advisor_events.c.id)
        with self._unit.connection() as connection:
            rows = connection.execute(statement).all()
        return tuple(_decode(row) for row in rows)

    def save(self, event: AdvisorEvent) -> AdvisorEvent:
        if event.tenant_id != self._tenant_id:
            raise ValueError("Tenant de evento de asesor invalido.")
        with self._unit.connection() as connection:
            result = connection.execute(
                update(advisor_events)
                .where(
                    advisor_events.c.id == str(event.id),
                    advisor_events.c.tenant_id == self._tenant_id,
                )
                .values(
                    status=event.status.value,
                    resolved_by=event.resolved_by,
                    resolved_at=event.resolved_at,
                    reason=event.reason,
                    client_notified=event.client_notified,
                )
            )
            if result.rowcount != 1:
                raise ValueError("Evento de asesor inexistente.")
        return event

    @contextmanager
    def review_transaction(self, event_id: UUID) -> Iterator[None]:
        with self._unit.transaction() as connection:
            # The funnel may update a quote before notifying the inbox. Lock in
            # that same order to avoid a cross-flow deadlock on reconfirmation.
            quote_id = connection.execute(
                select(advisor_events.c.quote_id).where(
                    advisor_events.c.id == str(event_id),
                    advisor_events.c.tenant_id == self._tenant_id,
                )
            ).scalar_one_or_none()
            if quote_id:
                connection.execute(
                    select(quote_drafts.c.id)
                    .where(
                        quote_drafts.c.id == quote_id,
                        quote_drafts.c.tenant_id == self._tenant_id,
                    )
                    .with_for_update()
                ).one_or_none()
            connection.execute(
                select(advisor_events.c.id)
                .where(
                    advisor_events.c.id == str(event_id),
                    advisor_events.c.tenant_id == self._tenant_id,
                )
                .with_for_update()
            ).one_or_none()
            yield
