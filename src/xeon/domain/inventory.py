from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from xeon.domain.money import parse_decimal


class InvalidInventoryError(ValueError):
    """Raised when a stock snapshot or availability query is not usable."""


class StockChannel(StrEnum):
    ON_HAND = "on_hand"
    DELIVERY = "delivery"


class AvailabilityKind(StrEnum):
    LOCAL = "local"
    TRANSFER = "transfer"
    DELIVERY = "delivery"


class FulfillmentStatus(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


def _require_text(value: str, *, field: str) -> str:
    text = value.strip()
    if not text:
        raise InvalidInventoryError(f"{field} es obligatorio.")
    return text


def as_non_negative_quantity(value: Decimal | int | str) -> Decimal:
    quantity = parse_decimal(value, error=InvalidInventoryError)
    if quantity < 0:
        raise InvalidInventoryError("La cantidad de inventario no puede ser negativa.")
    return quantity


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    sku: str
    branch_id: str | None
    origin_id: str
    origin_name: str
    quantity: Decimal
    channel: StockChannel
    source: str
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "sku", _require_text(self.sku, field="sku").upper())
        object.__setattr__(self, "origin_id", _require_text(self.origin_id, field="origin_id"))
        object.__setattr__(
            self, "origin_name", _require_text(self.origin_name, field="origin_name")
        )
        object.__setattr__(self, "source", _require_text(self.source, field="source"))
        object.__setattr__(
            self, "observed_at", _require_text(self.observed_at, field="observed_at")
        )
        object.__setattr__(self, "quantity", as_non_negative_quantity(self.quantity))
        branch_id = self.branch_id.strip() if self.branch_id is not None else None
        if branch_id == "":
            branch_id = None
        if self.channel is StockChannel.ON_HAND and branch_id is None:
            raise InvalidInventoryError("El inventario en sede requiere una sede.")
        if self.channel is StockChannel.DELIVERY and branch_id is not None:
            raise InvalidInventoryError("La entrega no se registra como inventario de sede.")
        object.__setattr__(self, "branch_id", branch_id)


def classify_availability(snapshot: StockSnapshot, *, requested_branch_id: str) -> AvailabilityKind:
    requested = _require_text(requested_branch_id, field="requested_branch_id")
    if snapshot.channel is StockChannel.DELIVERY:
        return AvailabilityKind.DELIVERY
    if snapshot.branch_id == requested:
        return AvailabilityKind.LOCAL
    return AvailabilityKind.TRANSFER


def as_positive_requested_quantity(value: Decimal | int | str) -> Decimal:
    quantity = parse_decimal(value, error=InvalidInventoryError)
    if quantity <= 0:
        raise InvalidInventoryError("La cantidad solicitada debe ser mayor que cero.")
    return quantity


@dataclass(frozen=True, slots=True)
class LocalFulfillment:
    status: FulfillmentStatus
    local_available: Decimal | None
    shortfall: Decimal | None


def explain_local_fulfillment(
    *,
    local_quantity: Decimal | None,
    requested_quantity: Decimal | int | str,
) -> LocalFulfillment:
    requested = as_positive_requested_quantity(requested_quantity)
    if local_quantity is None:
        return LocalFulfillment(
            status=FulfillmentStatus.UNKNOWN,
            local_available=None,
            shortfall=None,
        )
    available = as_non_negative_quantity(local_quantity)
    if available >= requested:
        return LocalFulfillment(
            status=FulfillmentStatus.SUFFICIENT,
            local_available=available,
            shortfall=Decimal("0"),
        )
    return LocalFulfillment(
        status=FulfillmentStatus.PARTIAL,
        local_available=available,
        shortfall=requested - available,
    )
