from __future__ import annotations

from typing import Protocol

from xeon.domain.cart import QuoteCart


class CartRepository(Protocol):
    def get(self, conversation_key: str) -> QuoteCart | None: ...

    def save(self, cart: QuoteCart) -> QuoteCart: ...
