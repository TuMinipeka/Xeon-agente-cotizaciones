from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from xeon.domain.money import DEFAULT_CURRENCY, CurrencyMismatchError, Money, parse_decimal
from xeon.domain.product import Product

INITIAL_QUOTE_VERSION = 1


class InvalidQuantityError(ValueError):
    """Raised when a commercial quantity is not usable."""


class EmptyQuoteError(ValueError):
    """Raised when a draft is requested without lines."""


class InvalidQuoteLineError(ValueError):
    """Raised when a quote line violates commercial invariants."""


class InvalidQuoteError(ValueError):
    """Raised when a quote violates commercial invariants."""


class QuoteStatus(StrEnum):
    DRAFT = "DRAFT"


def as_positive_quantity(value: Decimal | int | str) -> Decimal:
    quantity = parse_decimal(value, error=InvalidQuantityError)
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que cero.")
    return quantity


def _require_text(value: str, *, field: str, error: type[Exception]) -> str:
    text = value.strip()
    if not text:
        raise error(f"{field} es obligatorio.")
    return text


def _set_text(instance: object, field: str, value: str, error: type[Exception]) -> str:
    text = _require_text(value, field=field, error=error)
    object.__setattr__(instance, field, text)
    return text


@dataclass(frozen=True, slots=True)
class QuoteLine:
    product_id: str
    sku: str
    description: str
    unit: str
    quantity: Decimal
    unit_price: Money
    line_total: Money
    catalog_version: str
    source: str

    def __post_init__(self) -> None:
        _set_text(self, "product_id", self.product_id, InvalidQuoteLineError)
        _set_text(self, "sku", self.sku, InvalidQuoteLineError)
        _set_text(self, "description", self.description, InvalidQuoteLineError)
        _set_text(self, "unit", self.unit, InvalidQuoteLineError)
        _set_text(self, "catalog_version", self.catalog_version, InvalidQuoteLineError)
        _set_text(self, "source", self.source, InvalidQuoteLineError)
        quantity = as_positive_quantity(self.quantity)
        object.__setattr__(self, "quantity", quantity)
        if self.unit_price.currency != self.line_total.currency:
            raise CurrencyMismatchError("La linea debe usar una sola moneda.")
        expected = self.unit_price.times(quantity)
        if self.line_total != expected:
            raise InvalidQuoteLineError("El total de linea debe ser precio por cantidad.")


@dataclass(frozen=True, slots=True)
class Quote:
    id: UUID
    tenant_id: str
    request_id: str
    version: int
    status: QuoteStatus
    currency: str
    lines: tuple[QuoteLine, ...]
    subtotal: Money
    total: Money
    catalog_version: str
    source: str
    notes: str

    def __post_init__(self) -> None:
        _set_text(self, "tenant_id", self.tenant_id, InvalidQuoteError)
        _set_text(self, "request_id", self.request_id, InvalidQuoteError)
        _set_text(self, "catalog_version", self.catalog_version, InvalidQuoteError)
        _set_text(self, "source", self.source, InvalidQuoteError)
        _set_text(self, "notes", self.notes, InvalidQuoteError)
        currency = _require_text(self.currency, field="currency", error=InvalidQuoteError)
        object.__setattr__(self, "currency", currency.upper())
        if self.version < INITIAL_QUOTE_VERSION:
            raise InvalidQuoteError("La version del borrador debe ser al menos 1.")
        if self.status is not QuoteStatus.DRAFT:
            raise InvalidQuoteError("Este corte solo admite cotizaciones en DRAFT.")
        if not self.lines:
            raise EmptyQuoteError("Un borrador requiere al menos una linea.")
        if self.subtotal.currency != self.currency or self.total.currency != self.currency:
            raise CurrencyMismatchError("Cabecera y totales deben usar la misma moneda.")
        expected_subtotal = Money.zero(self.currency)
        for line in self.lines:
            if line.unit_price.currency != self.currency:
                raise CurrencyMismatchError("Todas las lineas deben usar la misma moneda.")
            expected_subtotal = expected_subtotal.plus(line.line_total)
        if self.subtotal != expected_subtotal:
            raise InvalidQuoteError("El subtotal debe ser la suma de las lineas.")
        if self.total != self.subtotal:
            raise InvalidQuoteError(
                "Sin politica de descuentos ni impuestos, total y subtotal coinciden."
            )


def build_quote_line(product: Product, quantity: Decimal | int | str) -> QuoteLine:
    parsed_quantity = as_positive_quantity(quantity)
    line_total = product.list_price.times(parsed_quantity)
    return QuoteLine(
        product_id=product.sku,
        sku=product.sku,
        description=product.name,
        unit=product.unit,
        quantity=parsed_quantity,
        unit_price=product.list_price,
        line_total=line_total,
        catalog_version=product.catalog_version,
        source=product.source,
    )


def build_draft_quote(
    lines: tuple[QuoteLine, ...],
    *,
    tenant_id: str,
    request_id: str,
    quote_id: UUID | None = None,
    notes: str = "Datos sinteticos de Ferreteria Demo XEON. No atribuir a una empresa real.",
) -> Quote:
    if not lines:
        raise EmptyQuoteError("Un borrador requiere al menos una linea.")

    currency = lines[0].unit_price.currency
    subtotal = Money.zero(currency)
    catalog_versions: set[str] = set()
    sources: set[str] = set()
    for line in lines:
        if line.unit_price.currency != currency:
            raise CurrencyMismatchError("Todas las lineas deben usar la misma moneda.")
        subtotal = subtotal.plus(line.line_total)
        catalog_versions.add(line.catalog_version)
        sources.add(line.source)

    catalog_version = next(iter(catalog_versions)) if len(catalog_versions) == 1 else "mixed"
    source = next(iter(sources)) if len(sources) == 1 else "synthetic-mixed"
    return Quote(
        id=quote_id or uuid4(),
        tenant_id=tenant_id,
        request_id=request_id,
        version=INITIAL_QUOTE_VERSION,
        status=QuoteStatus.DRAFT,
        currency=currency or DEFAULT_CURRENCY,
        lines=lines,
        subtotal=subtotal,
        total=subtotal,
        catalog_version=catalog_version,
        source=source,
        notes=notes,
    )
