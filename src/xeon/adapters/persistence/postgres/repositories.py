"""PostgreSQL implementations of the existing state ports."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from xeon.adapters.persistence.postgres.codec import (
    cart_in,
    cart_out,
    funnel_in,
    funnel_out,
    quote_in,
    quote_out,
)
from xeon.adapters.persistence.postgres.schema import (
    cart_states,
    funnel_states,
    processed_events,
    quote_drafts,
)
from xeon.adapters.persistence.postgres.unit import PostgresUnit
from xeon.application.ports.funnel import FunnelState
from xeon.domain.cart import QuoteCart
from xeon.domain.quote import Quote


class ConcurrentCartUpdate(RuntimeError):
    """The caller tried to replace a newer cart version."""


class PostgresFunnelRepository:
    def __init__(self, unit: PostgresUnit) -> None:
        self._unit = unit

    def conversation(self, key: str) -> AbstractAsyncContextManager[None]:
        return self._unit.conversation(key)

    def get(self, conversation_key: str) -> FunnelState:
        with self._unit.connection() as connection:
            row = connection.execute(
                select(funnel_states.c.payload).where(
                    funnel_states.c.conversation_key == self._unit.key(conversation_key)
                )
            ).scalar_one_or_none()
        return funnel_in(row) if row is not None else FunnelState()

    def save(self, conversation_key: str, state: FunnelState) -> None:
        values = {
            "conversation_key": self._unit.key(conversation_key),
            "payload": funnel_out(state),
        }
        statement = (
            insert(funnel_states)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[funnel_states.c.conversation_key],
                set_={"payload": values["payload"]},
            )
        )
        with self._unit.connection() as connection:
            connection.execute(statement)


class PostgresCartRepository:
    def __init__(self, unit: PostgresUnit) -> None:
        self._unit = unit

    def get(self, conversation_key: str) -> QuoteCart | None:
        with self._unit.connection() as connection:
            payload = connection.execute(
                select(cart_states.c.payload).where(
                    cart_states.c.conversation_key == self._unit.key(conversation_key)
                )
            ).scalar_one_or_none()
        return cart_in(payload) if payload is not None else None

    def save(self, cart: QuoteCart) -> QuoteCart:
        payload = cart_out(cart)
        key = self._unit.key(cart.conversation_key)
        with self._unit.connection() as connection:
            if cart.version == 0:
                inserted = connection.execute(
                    insert(cart_states)
                    .values(conversation_key=key, version=0, payload=payload)
                    .on_conflict_do_nothing(index_elements=[cart_states.c.conversation_key])
                    .returning(cart_states.c.conversation_key)
                ).scalar_one_or_none()
                if inserted is not None:
                    return cart
            row = connection.execute(
                select(cart_states.c.version, cart_states.c.payload)
                .where(cart_states.c.conversation_key == key)
                .with_for_update()
            ).one_or_none()
            if row is None:
                if cart.version != 1:
                    raise ConcurrentCartUpdate("Version inicial de carrito invalida.")
                inserted = connection.execute(
                    insert(cart_states)
                    .values(conversation_key=key, version=cart.version, payload=payload)
                    .on_conflict_do_nothing(index_elements=[cart_states.c.conversation_key])
                    .returning(cart_states.c.conversation_key)
                ).scalar_one_or_none()
                if inserted is None:
                    raise ConcurrentCartUpdate("La version inicial del carrito ya fue guardada.")
                return cart
            old_version = cast(int, row[0])
            old_payload = cast(dict[str, Any], row[1])
            if cart.version == old_version:
                old_cart = cart_in(old_payload)
                if cart.lines != old_cart.lines or cart.quote_version != old_cart.quote_version:
                    raise ConcurrentCartUpdate("La version del carrito ya cambio.")
            elif cart.version != old_version + 1:
                raise ConcurrentCartUpdate("La version del carrito ya cambio.")
            connection.execute(
                update(cart_states)
                .where(cart_states.c.conversation_key == key)
                .values(version=cart.version, payload=payload)
            )
        return cart


class PostgresQuoteDraftRepository:
    def __init__(self, unit: PostgresUnit) -> None:
        self._unit = unit

    def save(self, quote: Quote) -> Quote:
        if quote.tenant_id != self._unit.tenant_id:
            raise ValueError("Tenant de borrador invalido.")
        values = {
            "id": str(quote.id),
            "tenant_id": quote.tenant_id,
            "request_id": quote.request_id,
            "payload": quote_out(quote),
        }
        with self._unit.connection() as connection:
            inserted = connection.execute(
                insert(quote_drafts)
                .values(**values)
                .on_conflict_do_nothing()
                .returning(quote_drafts.c.id)
            ).scalar_one_or_none()
            if inserted is not None:
                return quote
            row = connection.execute(
                select(quote_drafts.c.id, quote_drafts.c.payload)
                .where(
                    quote_drafts.c.tenant_id == quote.tenant_id,
                    quote_drafts.c.request_id == quote.request_id,
                )
                .with_for_update()
            ).one()
            if row.id != str(quote.id):
                return quote_in(row.payload)
            connection.execute(
                update(quote_drafts)
                .where(quote_drafts.c.id == str(quote.id))
                .values(payload=values["payload"])
            )
        return quote

    def get(self, quote_id: UUID) -> Quote | None:
        with self._unit.connection() as connection:
            payload = connection.execute(
                select(quote_drafts.c.payload).where(
                    quote_drafts.c.id == str(quote_id),
                    quote_drafts.c.tenant_id == self._unit.tenant_id,
                )
            ).scalar_one_or_none()
        return quote_in(payload) if payload is not None else None

    def get_by_idempotency_key(self, tenant_id: str, request_id: str) -> Quote | None:
        if tenant_id != self._unit.tenant_id:
            return None
        with self._unit.connection() as connection:
            payload = connection.execute(
                select(quote_drafts.c.payload).where(
                    quote_drafts.c.tenant_id == tenant_id,
                    quote_drafts.c.request_id == request_id,
                )
            ).scalar_one_or_none()
        return quote_in(payload) if payload is not None else None


class PostgresProcessedEventStore:
    def __init__(self, unit: PostgresUnit, tenant_id: str) -> None:
        self._unit = unit
        self._tenant_id = tenant_id

    def claim(self, instance: str, message_id: str) -> bool:
        with self._unit.connection() as connection:
            result = connection.execute(
                insert(processed_events)
                .values(
                    tenant_id=self._tenant_id,
                    instance=instance,
                    message_id=message_id,
                )
                .on_conflict_do_nothing()
                .returning(processed_events.c.message_id)
            ).scalar_one_or_none()
        return result is not None
