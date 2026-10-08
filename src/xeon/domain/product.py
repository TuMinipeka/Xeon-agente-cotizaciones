from __future__ import annotations

from dataclasses import dataclass

from xeon.domain.money import Money


class InvalidProductError(ValueError):
    """Raised when a product cannot be constructed."""


@dataclass(frozen=True, slots=True)
class ProductId:
    value: str

    def __post_init__(self) -> None:
        sku = self.value.strip().upper()
        if not sku:
            raise InvalidProductError("ProductId no puede estar vacio.")
        object.__setattr__(self, "value", sku)


@dataclass(frozen=True, slots=True)
class Product:
    id: ProductId
    name: str
    unit: str
    list_price: Money
    aliases: tuple[str, ...]
    source: str
    catalog_version: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        unit = self.unit.strip()
        source = self.source.strip()
        catalog_version = self.catalog_version.strip()
        if not name:
            raise InvalidProductError("El nombre del producto es obligatorio.")
        if not unit:
            raise InvalidProductError("La unidad comercial es obligatoria.")
        if not source:
            raise InvalidProductError("La procedencia del producto es obligatoria.")
        if not catalog_version:
            raise InvalidProductError("La version del catalogo es obligatoria.")
        aliases = tuple(alias.strip() for alias in self.aliases if alias.strip())
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "catalog_version", catalog_version)
        object.__setattr__(self, "aliases", aliases)

    @property
    def sku(self) -> str:
        return self.id.value
