from __future__ import annotations

from uuid import UUID

from xeon.domain.quote import Quote


class InMemoryQuoteDraftRepository:
    def __init__(self) -> None:
        self._quotes: dict[UUID, Quote] = {}
        self._by_key: dict[tuple[str, str], Quote] = {}

    def save(self, quote: Quote) -> Quote:
        self._quotes[quote.id] = quote
        self._by_key[(quote.tenant_id, quote.request_id)] = quote
        return quote

    def get(self, quote_id: UUID) -> Quote | None:
        return self._quotes.get(quote_id)

    def get_by_idempotency_key(self, tenant_id: str, request_id: str) -> Quote | None:
        return self._by_key.get((tenant_id, request_id))
