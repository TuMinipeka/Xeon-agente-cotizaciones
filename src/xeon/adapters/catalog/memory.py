from __future__ import annotations

from xeon.application.ports.catalog import CatalogUnavailableError
from xeon.domain.money import Money
from xeon.domain.product import Product, ProductId

SYNTHETIC_CATALOG_VERSION = "synthetic-2026-10-08"
SYNTHETIC_SOURCE = "synthetic-ferreteria-demo-xeon"


def _product(
    sku: str,
    name: str,
    unit: str,
    amount: str,
    aliases: tuple[str, ...],
) -> Product:
    return Product(
        id=ProductId(sku),
        name=name,
        unit=unit,
        list_price=Money(amount, "COP"),
        aliases=aliases,
        source=SYNTHETIC_SOURCE,
        catalog_version=SYNTHETIC_CATALOG_VERSION,
    )


SYNTHETIC_PRODUCTS: tuple[Product, ...] = (
    _product(
        "CEM-50",
        "Cemento gris 50 kg",
        "bulto",
        "28900.00",
        ("cemento", "cemento 50kg", "bulto de cemento"),
    ),
    _product(
        "ALA-14",
        "Alambre de pua calibre 14",
        "metro",
        "1850.00",
        ("alambre", "alambre de pua", "alambre calibre 14"),
    ),
    _product(
        "TUB-PVC-20",
        "Tubo PVC presion 1/2 pulgada",
        "unidad",
        "4200.00",
        ("tubo pvc", "tubo 1/2"),
    ),
)


class InMemoryProductCatalog:
    """Exact SKU/alias lookup over a small synthetic catalog. Never invents prices."""

    def __init__(self, products: tuple[Product, ...] = SYNTHETIC_PRODUCTS) -> None:
        index: dict[str, Product] = {}
        for product in products:
            index[product.sku] = product
            for alias in product.aliases:
                index[alias.casefold()] = product
        self._index = index
        self._available = True

    def mark_unavailable(self) -> None:
        self._available = False

    def find_exact(self, query: str) -> Product | None:
        if not self._available:
            raise CatalogUnavailableError("El catalogo sintetico no esta disponible.")
        needle = query.strip()
        if not needle:
            return None
        by_sku = self._index.get(needle.upper())
        if by_sku is not None:
            return by_sku
        return self._index.get(needle.casefold())
