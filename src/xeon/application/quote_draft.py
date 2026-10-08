from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.ports.quotes import QuoteDraftRepository
from xeon.application.quote_request import ClarificationReason, classify_line_query
from xeon.domain.quote import EmptyQuoteError, Quote, QuoteLine, build_draft_quote, build_quote_line


@dataclass(frozen=True, slots=True)
class DraftLineRequest:
    query: str
    quantity: Decimal | int | str


@dataclass(frozen=True, slots=True)
class CreateQuoteDraftCommand:
    tenant_id: str
    request_id: str
    lines: tuple[DraftLineRequest, ...]
    discount_requested: bool = False


@dataclass(frozen=True, slots=True)
class QuoteDraftReady:
    quote: Quote
    replayed: bool


@dataclass(frozen=True, slots=True)
class ClarificationRequired:
    query: str
    reason: ClarificationReason
    message: str


@dataclass(frozen=True, slots=True)
class ProductNotFound:
    query: str
    message: str


@dataclass(frozen=True, slots=True)
class CatalogUnavailable:
    message: str


@dataclass(frozen=True, slots=True)
class DiscountPolicyUnavailable:
    message: str


CreateQuoteResult = (
    QuoteDraftReady
    | ClarificationRequired
    | ProductNotFound
    | CatalogUnavailable
    | DiscountPolicyUnavailable
)


class QuoteNotFoundError(LookupError):
    """Raised when a draft does not exist for the requesting tenant."""


def _require_key_part(value: str, *, name: str) -> str:
    text = value.strip()
    if not text:
        raise EmptyQuoteError(f"{name} es obligatorio.")
    return text


class CreateQuoteDraft:
    def __init__(self, catalog: ProductCatalog, quotes: QuoteDraftRepository) -> None:
        self._catalog = catalog
        self._quotes = quotes

    def execute(self, command: CreateQuoteDraftCommand) -> CreateQuoteResult:
        tenant_id = _require_key_part(command.tenant_id, name="tenant_id")
        request_id = _require_key_part(command.request_id, name="request_id")
        existing = self._quotes.get_by_idempotency_key(tenant_id, request_id)
        if existing is not None:
            return QuoteDraftReady(quote=existing, replayed=True)

        if command.discount_requested:
            return DiscountPolicyUnavailable(
                "No hay una politica de descuentos sintetica aprobada; "
                "el backend no inventa el porcentaje."
            )
        if not command.lines:
            raise EmptyQuoteError("Un borrador requiere al menos una linea.")

        lines: list[QuoteLine] = []
        try:
            for request in command.lines:
                classified = classify_line_query(request.query)
                if classified.reason == "missing_units":
                    return ClarificationRequired(
                        query=request.query,
                        reason="missing_units",
                        message=(
                            "Faltan unidades y contexto; esas medidas no determinan una referencia."
                        ),
                    )
                product = self._catalog.find_exact(request.query)
                if product is not None:
                    lines.append(build_quote_line(product, request.quantity))
                    continue
                if classified.reason == "ambiguous_reference":
                    return ClarificationRequired(
                        query=request.query,
                        reason="ambiguous_reference",
                        message=(
                            "La referencia es ambigua; se necesitan caracteristicas "
                            "antes de seleccionar un SKU."
                        ),
                    )
                return ProductNotFound(
                    query=request.query,
                    message=(
                        f"No existe un producto exacto para {request.query!r}; "
                        "desconocido no significa existencia cero."
                    ),
                )
        except CatalogUnavailableError:
            return CatalogUnavailable(
                "El catalogo sintetico no esta disponible; no se puede confirmar existencia."
            )

        draft = build_draft_quote(tuple(lines), tenant_id=tenant_id, request_id=request_id)
        return QuoteDraftReady(quote=self._quotes.save(draft), replayed=False)


class GetQuoteDraft:
    def __init__(self, quotes: QuoteDraftRepository) -> None:
        self._quotes = quotes

    def execute(self, quote_id: UUID, tenant_id: str) -> Quote:
        quote = self._quotes.get(quote_id)
        if quote is None or quote.tenant_id != tenant_id.strip():
            raise QuoteNotFoundError(str(quote_id))
        return quote
