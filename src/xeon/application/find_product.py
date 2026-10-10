from __future__ import annotations

from dataclasses import dataclass

from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.quote_draft import CatalogUnavailable, ClarificationRequired, ProductNotFound
from xeon.application.quote_request import classify_line_query
from xeon.domain.product import Product


@dataclass(frozen=True, slots=True)
class ProductFound:
    product: Product
    query: str


FindProductResult = ProductFound | ClarificationRequired | ProductNotFound | CatalogUnavailable


class FindProduct:
    def __init__(self, catalog: ProductCatalog) -> None:
        self._catalog = catalog

    def execute(self, query: str) -> FindProductResult:
        classified = classify_line_query(query)
        if classified.reason == "missing_units":
            return ClarificationRequired(
                query=query,
                reason="missing_units",
                message=("Faltan unidades y contexto; esas medidas no determinan una referencia."),
            )
        try:
            product = self._catalog.find_exact(query)
        except CatalogUnavailableError:
            return CatalogUnavailable(
                "El catalogo sintetico no esta disponible; no se puede confirmar existencia."
            )
        if product is not None:
            return ProductFound(product=product, query=query)
        if classified.reason == "ambiguous_reference":
            return ClarificationRequired(
                query=query,
                reason="ambiguous_reference",
                message=(
                    "La referencia es ambigua; se necesitan caracteristicas "
                    "antes de seleccionar un SKU."
                ),
            )
        return ProductNotFound(
            query=query,
            message=(
                f"No existe un producto exacto para {query!r}; "
                "desconocido no significa existencia cero."
            ),
        )
