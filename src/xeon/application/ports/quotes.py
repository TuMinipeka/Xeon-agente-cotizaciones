from __future__ import annotations

from typing import Protocol
from uuid import UUID

from xeon.domain.quote import Quote


class QuoteDraftRepository(Protocol):
    def save(self, quote: Quote) -> Quote:
        """Persist a DRAFT quote and return the stored copy."""

    def get(self, quote_id: UUID) -> Quote | None:
        """Load a previously stored draft, if it exists."""

    def get_by_idempotency_key(self, tenant_id: str, request_id: str) -> Quote | None:
        """Return the draft already stored for tenant_id + request_id."""
