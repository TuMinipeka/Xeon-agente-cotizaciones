"""PostgreSQL lease queues for signed inbound events and outbound Kapso sends."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from xeon.adapters.persistence.postgres.codec import reply_in, reply_out
from xeon.adapters.persistence.postgres.schema import (
    advisor_events,
    inbound_deliveries,
    outbound_deliveries,
)
from xeon.adapters.persistence.postgres.unit import PostgresUnit
from xeon.application.ports.channels import IncomingWhatsAppMessage
from xeon.application.ports.delivery import ClaimedInbound, ClaimedOutbound
from xeon.application.reply import Reply

LEASE_SECONDS = 180
MAX_ATTEMPTS = 5


def _delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(2 ** min(attempts, 8), 300))


class PostgresInboundQueue:
    def __init__(self, unit: PostgresUnit) -> None:
        self._unit = unit

    def put(self, message: IncomingWhatsAppMessage) -> bool:
        with self._unit.connection() as connection:
            inserted = connection.execute(
                insert(inbound_deliveries)
                .values(
                    tenant_id=self._unit.tenant_id,
                    instance=message.instance,
                    message_id=message.external_message_id,
                    sender_jid=message.sender_jid,
                    sender_number=message.sender_number,
                    text=message.text,
                    option_id=message.option_id,
                    raw_payload=message.raw_payload,
                    received_at=datetime.now(UTC),
                    status="pending",
                    attempts=0,
                    available_at=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
                .returning(inbound_deliveries.c.message_id)
            ).scalar_one_or_none()
        return inserted is not None

    def claim_due(self) -> ClaimedInbound | None:
        now = datetime.now(UTC)
        earlier = inbound_deliveries.alias("earlier_inbound")
        with self._unit.connection() as connection:
            row = connection.execute(
                select(inbound_deliveries)
                .where(
                    inbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    inbound_deliveries.c.status == "pending",
                    inbound_deliveries.c.available_at <= now,
                    or_(
                        inbound_deliveries.c.claim_until.is_(None),
                        inbound_deliveries.c.claim_until <= now,
                    ),
                    ~select(1)
                    .where(
                        earlier.c.tenant_id == inbound_deliveries.c.tenant_id,
                        earlier.c.instance == inbound_deliveries.c.instance,
                        earlier.c.sender_number == inbound_deliveries.c.sender_number,
                        earlier.c.status == "pending",
                        or_(
                            earlier.c.received_at < inbound_deliveries.c.received_at,
                            and_(
                                earlier.c.received_at == inbound_deliveries.c.received_at,
                                earlier.c.message_id < inbound_deliveries.c.message_id,
                            ),
                        ),
                    )
                    .exists(),
                )
                .order_by(inbound_deliveries.c.received_at, inbound_deliveries.c.message_id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).one_or_none()
            if row is None:
                return None
            token = str(uuid4())
            attempts = row.attempts + 1
            connection.execute(
                update(inbound_deliveries)
                .where(
                    inbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    inbound_deliveries.c.instance == row.instance,
                    inbound_deliveries.c.message_id == row.message_id,
                )
                .values(
                    claim_token=token,
                    claim_until=now + timedelta(seconds=LEASE_SECONDS),
                    attempts=attempts,
                )
            )
        message = IncomingWhatsAppMessage(
            instance=row.instance,
            external_message_id=row.message_id,
            sender_jid=row.sender_jid,
            sender_number=row.sender_number,
            text=row.text,
            raw_payload=row.raw_payload,
            option_id=row.option_id,
        )
        return ClaimedInbound(message, token, attempts)

    def complete(self, claimed: ClaimedInbound) -> None:
        with self._unit.connection() as connection:
            result = connection.execute(
                update(inbound_deliveries)
                .where(
                    inbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    inbound_deliveries.c.instance == claimed.message.instance,
                    inbound_deliveries.c.message_id == claimed.message.external_message_id,
                    inbound_deliveries.c.claim_token == claimed.token,
                )
                .values(status="done", claim_token=None, claim_until=None)
            )
            if result.rowcount != 1:
                raise RuntimeError("Lease de webhook vencido.")

    def retry(self, claimed: ClaimedInbound) -> None:
        permanent = claimed.attempts >= MAX_ATTEMPTS
        with self._unit.connection() as connection:
            connection.execute(
                update(inbound_deliveries)
                .where(
                    inbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    inbound_deliveries.c.instance == claimed.message.instance,
                    inbound_deliveries.c.message_id == claimed.message.external_message_id,
                    inbound_deliveries.c.claim_token == claimed.token,
                )
                .values(
                    status="failed" if permanent else "pending",
                    available_at=datetime.now(UTC) + _delay(claimed.attempts),
                    claim_token=None,
                    claim_until=None,
                )
            )


class PostgresOutboundQueue:
    def __init__(self, unit: PostgresUnit) -> None:
        self._unit = unit

    def put(
        self,
        *,
        key: str,
        recipient_number: str,
        reply: Reply,
        advisor_event_id: UUID | None = None,
    ) -> bool:
        with self._unit.connection() as connection:
            inserted = connection.execute(
                insert(outbound_deliveries)
                .values(
                    tenant_id=self._unit.tenant_id,
                    send_key=key,
                    recipient_number=recipient_number,
                    reply=reply_out(reply),
                    created_at=datetime.now(UTC),
                    advisor_event_id=str(advisor_event_id) if advisor_event_id else None,
                    status="pending",
                    attempts=0,
                    available_at=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
                .returning(outbound_deliveries.c.send_key)
            ).scalar_one_or_none()
        return inserted is not None

    def claim_due(self) -> ClaimedOutbound | None:
        now = datetime.now(UTC)
        earlier = outbound_deliveries.alias("earlier_outbound")
        with self._unit.connection() as connection:
            row = connection.execute(
                select(outbound_deliveries)
                .where(
                    outbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    outbound_deliveries.c.status == "pending",
                    outbound_deliveries.c.available_at <= now,
                    or_(
                        outbound_deliveries.c.claim_until.is_(None),
                        outbound_deliveries.c.claim_until <= now,
                    ),
                    ~select(1)
                    .where(
                        earlier.c.tenant_id == outbound_deliveries.c.tenant_id,
                        earlier.c.recipient_number == outbound_deliveries.c.recipient_number,
                        earlier.c.status == "pending",
                        or_(
                            earlier.c.created_at < outbound_deliveries.c.created_at,
                            and_(
                                earlier.c.created_at == outbound_deliveries.c.created_at,
                                earlier.c.send_key < outbound_deliveries.c.send_key,
                            ),
                        ),
                    )
                    .exists(),
                )
                .order_by(outbound_deliveries.c.created_at, outbound_deliveries.c.send_key)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).one_or_none()
            if row is None:
                return None
            token = str(uuid4())
            attempts = row.attempts + 1
            connection.execute(
                update(outbound_deliveries)
                .where(
                    outbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    outbound_deliveries.c.send_key == row.send_key,
                )
                .values(
                    claim_token=token,
                    claim_until=now + timedelta(seconds=LEASE_SECONDS),
                    attempts=attempts,
                )
            )
        return ClaimedOutbound(
            row.send_key, row.recipient_number, reply_in(row.reply), token, attempts
        )

    def sent(self, claimed: ClaimedOutbound, provider_message_id: str | None) -> None:
        with self._unit.connection() as connection:
            row = connection.execute(
                update(outbound_deliveries)
                .where(
                    outbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    outbound_deliveries.c.send_key == claimed.key,
                    outbound_deliveries.c.claim_token == claimed.token,
                )
                .values(
                    status="sent",
                    claim_token=None,
                    claim_until=None,
                    provider_message_id=provider_message_id,
                )
                .returning(outbound_deliveries.c.advisor_event_id)
            ).one_or_none()
            if row is not None and row.advisor_event_id:
                connection.execute(
                    update(advisor_events)
                    .where(
                        advisor_events.c.id == row.advisor_event_id,
                        advisor_events.c.tenant_id == self._unit.tenant_id,
                    )
                    .values(client_notified=True)
                )

    def failed(self, claimed: ClaimedOutbound, *, permanent: bool, status_code: int | None) -> None:
        final = permanent or claimed.attempts >= MAX_ATTEMPTS
        with self._unit.connection() as connection:
            row = connection.execute(
                update(outbound_deliveries)
                .where(
                    outbound_deliveries.c.tenant_id == self._unit.tenant_id,
                    outbound_deliveries.c.send_key == claimed.key,
                    outbound_deliveries.c.claim_token == claimed.token,
                )
                .values(
                    status="failed" if final else "pending",
                    available_at=datetime.now(UTC) + _delay(claimed.attempts),
                    claim_token=None,
                    claim_until=None,
                    last_status_code=status_code,
                )
                .returning(outbound_deliveries.c.advisor_event_id)
            ).one_or_none()
            if row is not None and row.advisor_event_id and final:
                connection.execute(
                    update(advisor_events)
                    .where(
                        advisor_events.c.id == row.advisor_event_id,
                        advisor_events.c.tenant_id == self._unit.tenant_id,
                    )
                    .values(client_notified=False)
                )
