from decimal import Decimal

import pytest

from xeon.adapters.catalog.synthetic_seed import ADDITIONAL_CORE_PRODUCTS, CORE_SYNTHETIC_PRODUCTS
from xeon.adapters.conversation.cart import InMemoryCartRepository
from xeon.domain.cart import QuoteCart
from xeon.domain.quote import build_draft_quote


def _product(sku: str):  # type: ignore[no-untyped-def]
    return next(
        product
        for product in CORE_SYNTHETIC_PRODUCTS + ADDITIONAL_CORE_PRODUCTS
        if product.sku == sku
    )


def test_cart_keeps_confirmed_quantities_and_selects_ambiguous_variant() -> None:
    cart = QuoteCart("conversation-1")
    cart = cart.add_item(_product("CEM-50"), 20)
    first = build_draft_quote(
        cart.confirmed_lines(), tenant_id="demo", request_id="turn-1", version=cart.version
    )
    assert first.version == 1
    cart = cart.set_quantity("CEM-50", 15).add_item(None, 2, label="pala")
    assert cart.version == 3
    assert len(cart.confirmed_lines()) == 1
    cart = cart.remove_item("pala", 1).choose_variant("pala", _product("PAL-RED-FIB"))
    current = build_draft_quote(
        cart.confirmed_lines(), tenant_id="demo", request_id="turn-4", version=cart.version
    )
    assert current.version == 5
    assert cart.quote_version == 3
    assert [(line.sku, line.quantity) for line in current.lines] == [
        ("CEM-50", Decimal(15)),
        ("PAL-RED-FIB", Decimal(1)),
    ]
    assert current.total.amount == Decimal("477200.00")


def test_cart_repository_is_scoped_by_conversation_and_clear_is_versioned() -> None:
    repository = InMemoryCartRepository(max_conversations=2)
    saved = repository.save(QuoteCart("a").add_item(_product("CEM-50"), 10))
    assert repository.get("a") == saved
    assert repository.get("b") is None
    cleared = repository.save(saved.clear())
    assert cleared.version == 2
    assert cleared.lines == ()
    with pytest.raises(LookupError):
        cleared.remove_item("CEM-50")
