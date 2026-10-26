from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError

from xeon.adapters.sql.connection import SqlReader, mapped
from xeon.application.ports.catalog import CatalogUnavailableError
from xeon.connectors.schema import ConnectorConfig, ReadQuery
from xeon.domain.money import Money
from xeon.domain.product import Product, ProductId


class SqlProductCatalog:
    def __init__(self, reader: SqlReader, config: ConnectorConfig, *, currency: str) -> None:
        self._reader = reader
        self._config = config
        self._currency = currency

    def _product(self, row: dict[str, object], query: ReadQuery) -> Product:
        raw_price = mapped(row, query, "price")
        if isinstance(raw_price, float):
            raise ValueError("El precio SQL debe ser decimal o texto, nunca float.")
        unit = str(mapped(row, query, "unit", "unidad"))
        aliases_raw = mapped(row, query, "aliases", "")
        aliases = tuple(
            alias.strip() for alias in str(aliases_raw or "").split("|") if alias.strip()
        )
        return Product(
            id=ProductId(str(mapped(row, query, "sku"))),
            name=str(mapped(row, query, "name")),
            unit=self._config.unit_map.get(unit, unit),
            list_price=Money(Decimal(str(raw_price)) / self._config.price_divisor, self._currency),
            aliases=aliases,
            source="sql-connector",
            catalog_version=self._config.catalog_version,
        )

    def find_exact(self, query: str) -> Product | None:
        try:
            rows = self._reader.rows(self._config.find_by_sku, sku=query.strip())
        except SQLAlchemyError as exc:
            raise CatalogUnavailableError("No se pudo consultar el catalogo SQL.") from exc
        return self._product(dict(rows[0]), self._config.find_by_sku) if rows else None

    def search_candidates(self, query: str, *, limit: int = 3) -> tuple[Product, ...]:
        if limit <= 0:
            return ()
        try:
            rows = self._reader.rows(
                self._config.search_text, query=f"%{query.strip()}%", limit=limit
            )
        except SQLAlchemyError as exc:
            raise CatalogUnavailableError("No se pudo consultar el catalogo SQL.") from exc
        return tuple(self._product(dict(row), self._config.search_text) for row in rows[:limit])
