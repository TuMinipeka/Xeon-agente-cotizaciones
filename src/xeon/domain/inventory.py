from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


def _require_text(value: str, *, field: str) -> str:
    text = value.strip()
    if not text:
        raise InvalidInventoryError(f"{field} es obligatorio.")
    return text


def _parse_utc_instant(value: str, *, field: str) -> datetime:
    text = _require_text(value, field=field)
    try:
        instant = datetime.fromisoformat(text)
    except ValueError as exc:
        raise InvalidInventoryError(f"{field} debe ser un instante UTC.") from exc
    if instant.tzinfo is None:
        raise InvalidInventoryError(f"{field} debe incluir zona horaria UTC.")
    return instant.astimezone(UTC)


def _iso8601_duration(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        raise InvalidInventoryError("evaluated_at no puede ser anterior a observed_at.")
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if minutes == 0 and seconds == 0:
        return f"PT{hours}H"
    if seconds == 0:
        return f"PT{hours}H{minutes}M"
    return f"PT{hours}H{minutes}M{seconds}S"


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
    valid_until: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sku", _require_text(self.sku, field="sku").upper())
        object.__setattr__(self, "origin_id", _require_text(self.origin_id, field="origin_id"))
        object.__setattr__(
            self, "origin_name", _require_text(self.origin_name, field="origin_name")
        )
        object.__setattr__(self, "source", _require_text(self.source, field="source"))
        observed_at = _require_text(self.observed_at, field="observed_at")
        _parse_utc_instant(observed_at, field="observed_at")
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "quantity", as_non_negative_quantity(self.quantity))
        branch_id = self.branch_id.strip() if self.branch_id is not None else None
        if branch_id == "":
            branch_id = None
        if self.channel is StockChannel.ON_HAND and branch_id is None:
            raise InvalidInventoryError("El inventario en sede requiere una sede.")
        if self.channel is StockChannel.DELIVERY and branch_id is not None:
            raise InvalidInventoryError("La entrega no se registra como inventario de sede.")
        object.__setattr__(self, "branch_id", branch_id)
        valid_until = self.valid_until.strip() if self.valid_until is not None else None
        if valid_until == "":
            valid_until = None
        if valid_until is not None:
            _parse_utc_instant(valid_until, field="valid_until")
        object.__setattr__(self, "valid_until", valid_until)


def classify_availability(snapshot: StockSnapshot, *, requested_branch_id: str) -> AvailabilityKind:
    requested = _require_text(requested_branch_id, field="requested_branch_id")
    if snapshot.channel is StockChannel.DELIVERY:
        return AvailabilityKind.DELIVERY
    if snapshot.branch_id == requested:
        return AvailabilityKind.LOCAL
    return AvailabilityKind.TRANSFER


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    freshness: Freshness
    is_firm: bool
    age: str


def classify_freshness(snapshot: StockSnapshot, *, evaluated_at: str) -> Freshness:
    instant = _parse_utc_instant(evaluated_at, field="evaluated_at")
    if snapshot.valid_until is None:
        return Freshness.UNKNOWN
    valid_until = _parse_utc_instant(snapshot.valid_until, field="valid_until")
    if instant <= valid_until:
        return Freshness.FRESH
    return Freshness.STALE


def assess_freshness(snapshot: StockSnapshot, *, evaluated_at: str) -> FreshnessAssessment:
    freshness = classify_freshness(snapshot, evaluated_at=evaluated_at)
    observed = _parse_utc_instant(snapshot.observed_at, field="observed_at")
    instant = _parse_utc_instant(evaluated_at, field="evaluated_at")
    return FreshnessAssessment(
        freshness=freshness,
        is_firm=freshness is Freshness.FRESH,
        age=_iso8601_duration(instant - observed),
    )


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
    freshness: Freshness | None = None,
) -> LocalFulfillment:
    requested = as_positive_requested_quantity(requested_quantity)
    if local_quantity is None or freshness in {Freshness.STALE, Freshness.UNKNOWN}:
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
