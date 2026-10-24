from __future__ import annotations

from xeon.adapters.catalog.synthetic_seed import (
    SYNTHETIC_CATALOG_SIZE,
    SYNTHETIC_PRODUCTS,
    SYNTHETIC_SOURCE,
)


def test_synthetic_seed_contains_two_thousand_tagged_references() -> None:
    assert len(SYNTHETIC_PRODUCTS) == SYNTHETIC_CATALOG_SIZE == 2_000
    assert all(product.source == SYNTHETIC_SOURCE for product in SYNTHETIC_PRODUCTS)
    assert any(product.sku == "LAM-ZIN-28-244" for product in SYNTHETIC_PRODUCTS)
