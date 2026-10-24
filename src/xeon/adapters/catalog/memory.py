from __future__ import annotations

import re
import unicodedata

from xeon.adapters.catalog.synthetic_seed import (
    SYNTHETIC_PRODUCTS as SEEDED_SYNTHETIC_PRODUCTS,
)
from xeon.application.ports.catalog import CatalogUnavailableError
from xeon.domain.money import Money
from xeon.domain.product import Product, ProductId

SYNTHETIC_CATALOG_VERSION = "synthetic-2026-10-08"
SYNTHETIC_SOURCE = "synthetic-ferreteria-demo-xeon"

_STOPWORDS = frozenset(
    {
        "de",
        "del",
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "para",
        "con",
        "por",
        "en",
        "que",
        "se",
        "al",
        "lo",
        "como",
        "mas",
        "mi",
        "necesito",
        "busco",
        "quiero",
        "tienen",
        "hay",
        "dame",
        "cotizar",
    }
)


def _tokenize(text: str) -> set[str]:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = re.findall(r"[a-z0-9/]+", normalized)
    return {
        token[:-1] if token.endswith("s") and len(token) > 3 else token
        for token in tokens
        if len(token) >= 2 and token not in _STOPWORDS and not token.isdigit()
    }


_UNIT_HINTS = {
    "bulto": "bulto",
    "lamina": "lamina",
    "metro": "metro",
    "rollo": "rollo",
    "caja": "caja",
    "galon": "galon",
    "libra": "libra",
    "par": "par",
}


def _product(
    sku: str,
    name: str,
    unit: str,
    amount: str,
    aliases: tuple[str, ...],
    *,
    specs: tuple[tuple[str, str], ...] = (),
    description_context: str = "",
) -> Product:
    return Product(
        id=ProductId(sku),
        name=name,
        unit=unit,
        list_price=Money(amount, "COP"),
        aliases=aliases,
        source=SYNTHETIC_SOURCE,
        catalog_version=SYNTHETIC_CATALOG_VERSION,
        specs=specs,
        description_context=description_context,
    )


SYNTHETIC_PRODUCTS: tuple[Product, ...] = (
    _product(
        "CEM-50",
        "Cemento gris 50 kg",
        "bulto",
        "28900.00",
        ("cemento", "cemento 50kg", "bulto de cemento"),
        specs=(
            ("peso_kg", "50"),
            ("tipo", "uso general y estructural"),
            ("norma", "NTC 121"),
        ),
        description_context=(
            "Cemento gris portland para mezcla de concreto, mortero, fundir placa, "
            "pegar ladrillo, bloque, repello, pañete, piso y obra gris en construccion."
        ),
    ),
    _product(
        "ALA-14",
        "Alambre de pua calibre 14",
        "metro",
        "1850.00",
        ("alambre", "alambre de pua", "alambre calibre 14"),
        specs=(
            ("calibre", "14"),
            ("recubrimiento", "galvanizado"),
            ("uso", "cercas ganaderas y linderos"),
        ),
        description_context=(
            "Alambre de puas galvanizado calibre 14 para cercar finca, potrero, "
            "ganado, lotes, postes de cerca y cerramiento rural agroferretero."
        ),
    ),
    _product(
        "TUB-PVC-20",
        "Tubo PVC presion 1/2 pulgada",
        "unidad",
        "4200.00",
        ("tubo pvc", "tubo 1/2"),
        specs=(
            ("diametro", "1/2 pulgada"),
            ("diametro_mm", "20"),
            ("presion_psi", "200"),
            ("fluido", "agua fria a presion"),
        ),
        description_context=(
            "Tubo de PVC blanco para conduccion de agua fria potable a presion, "
            "plomeria, hidraulica, tuberia de media pulgada para bano, cocina y acueducto."
        ),
    ),
)

# Keep the three original fixtures above readable for historical tests while the
# active in-memory catalog uses the reproducible 2,000-reference demo seed.
SYNTHETIC_PRODUCTS = SEEDED_SYNTHETIC_PRODUCTS


class InMemoryProductCatalog:
    """Hybrid lookup over a synthetic catalog: exact SKU/alias + semantic/specs candidate search."""

    def __init__(self, products: tuple[Product, ...] = SYNTHETIC_PRODUCTS) -> None:
        index: dict[str, Product] = {}
        for product in products:
            index[product.sku] = product
            for alias in product.aliases:
                index[alias.casefold()] = product
        self._products = products
        self._index = index
        self._available = True

    def mark_unavailable(self) -> None:
        self._available = False

    @property
    def products(self) -> tuple[Product, ...]:
        return self._products

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

    def search_candidates(self, query: str, *, limit: int = 3) -> tuple[Product, ...]:
        if not self._available:
            raise CatalogUnavailableError("El catalogo sintetico no esta disponible.")
        if limit <= 0:
            return ()
        exact = self.find_exact(query)
        if exact is not None:
            return (exact,)

        query_tokens = _tokenize(query)
        if not query_tokens:
            return ()
        requested_units = {unit for token, unit in _UNIT_HINTS.items() if token in query_tokens}

        scored: list[tuple[int, Product]] = []
        for product in self._products:
            if requested_units and product.unit.casefold() not in requested_units:
                continue
            name_tokens = _tokenize(product.name)
            alias_tokens = _tokenize(" ".join(product.aliases))
            specs_tokens = _tokenize(" ".join(f"{key} {val}" for key, val in product.specs))
            context_tokens = _tokenize(product.description_context)

            score = (
                3 * len(query_tokens & (name_tokens | alias_tokens))
                + 2 * len(query_tokens & specs_tokens)
                + 1 * len(query_tokens & context_tokens)
            )
            if "referencia_sintetica" in product.specs_dict:
                score -= 2
            if score > 0:
                scored.append((score, product))

        scored.sort(key=lambda item: (-item[0], item[1].sku))
        return tuple(product for _, product in scored[:limit])
