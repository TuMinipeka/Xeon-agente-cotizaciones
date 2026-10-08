from __future__ import annotations

from typing import Protocol

from xeon.domain.product import Product


class CatalogUnavailableError(RuntimeError):
    """Raised when the catalog source cannot be consulted."""


class ProductCatalog(Protocol):
    def find_exact(self, query: str) -> Product | None:
        """Return a product when SKU or alias matches exactly; never invent one."""
