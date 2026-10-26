from __future__ import annotations

from collections import OrderedDict

from xeon.domain.cart import QuoteCart


class InMemoryCartRepository:
    """Process-local cart storage, bounded by conversation count."""

    def __init__(self, *, max_conversations: int = 1000) -> None:
        if max_conversations < 1:
            raise ValueError("max_conversations debe ser positivo.")
        self._max_conversations = max_conversations
        self._carts: OrderedDict[str, QuoteCart] = OrderedDict()

    def get(self, conversation_key: str) -> QuoteCart | None:
        cart = self._carts.get(conversation_key)
        if cart is not None:
            self._carts.move_to_end(conversation_key)
        return cart

    def save(self, cart: QuoteCart) -> QuoteCart:
        self._carts[cart.conversation_key] = cart
        self._carts.move_to_end(cart.conversation_key)
        while len(self._carts) > self._max_conversations:
            self._carts.popitem(last=False)
        return cart
