from decimal import Decimal

from xeon.adapters.inventory.memory import InMemoryBranchInventory
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery
from xeon.domain.inventory import (
    AvailabilityKind,
    Freshness,
    FulfillmentStatus,
    StockChannel,
    StockSnapshot,
)

EVALUATED_AT = "2026-10-08T15:00:00+00:00"
EVALUATED_AFTER_EXPIRY = "2026-10-09T12:00:00+00:00"
VALID_UNTIL = "2026-10-08T18:00:00+00:00"
OBSERVED_AT = "2026-10-08T12:00:00+00:00"


def _snapshot(
    *,
    sku: str = "CEM-50",
    branch_id: str | None = "sede-centro",
    origin_id: str | None = None,
    origin_name: str = "Ferreteria Demo XEON Centro",
    quantity: str = "80",
    channel: StockChannel = StockChannel.ON_HAND,
    valid_until: str | None = VALID_UNTIL,
) -> StockSnapshot:
    resolved_origin = (
        origin_id if origin_id is not None else (branch_id or "origen-entrega-sintetica")
    )
    return StockSnapshot(
        sku=sku,
        branch_id=branch_id,
        origin_id=resolved_origin,
        origin_name=origin_name,
        quantity=Decimal(quantity),
        channel=channel,
        source="synthetic-ferreteria-demo-xeon",
        observed_at=OBSERVED_AT,
        valid_until=valid_until,
    )


def test_alternative_branch_is_not_reported_as_local_stock() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="TUB-PVC-20",
            requested_branch_id="sede-centro",
            evaluated_at=EVALUATED_AT,
        )
    )

    assert result.sku == "TUB-PVC-20"
    assert result.requested_branch_id == "sede-centro"
    assert result.items
    assert all(item.kind is not AvailabilityKind.LOCAL for item in result.items)
    transfer = next(item for item in result.items if item.kind is AvailabilityKind.TRANSFER)
    assert transfer.origin_id == "sede-norte"
    assert transfer.origin_name
    assert transfer.source == "synthetic-ferreteria-demo-xeon"
    assert transfer.quantity == Decimal("12")


def test_stock_response_keeps_origin_and_availability_kind() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-centro",
            evaluated_at=EVALUATED_AT,
        )
    )

    kinds = {item.kind for item in result.items}
    assert AvailabilityKind.LOCAL in kinds
    assert AvailabilityKind.TRANSFER in kinds
    assert AvailabilityKind.DELIVERY in kinds

    local = next(item for item in result.items if item.kind is AvailabilityKind.LOCAL)
    assert local.origin_id == "sede-centro"
    assert local.branch_id == "sede-centro"

    transfer = next(item for item in result.items if item.kind is AvailabilityKind.TRANSFER)
    assert transfer.origin_id == "sede-norte"
    assert transfer.branch_id == "sede-norte"
    assert transfer.kind is not AvailabilityKind.LOCAL

    delivery = next(item for item in result.items if item.kind is AvailabilityKind.DELIVERY)
    assert delivery.origin_id == "origen-entrega-sintetica"
    assert delivery.branch_id is None
    assert delivery.kind is AvailabilityKind.DELIVERY


def test_unknown_sku_does_not_invent_stock() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="SKU-INEXISTENTE",
            requested_branch_id="sede-centro",
            evaluated_at=EVALUATED_AT,
        )
    )

    assert result.items == ()


def test_partial_local_stock_reports_exact_shortfall_and_unreserved_alternatives() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-norte",
            requested_quantity="50",
            evaluated_at=EVALUATED_AT,
        )
    )

    assert result.requested_quantity == Decimal("50")
    assert result.fulfillment_status is FulfillmentStatus.PARTIAL
    assert result.local_available == Decimal("20")
    assert result.shortfall == Decimal("30")
    assert {item.kind for item in result.alternatives} == {
        AvailabilityKind.TRANSFER,
        AvailabilityKind.DELIVERY,
    }
    assert all(item.kind is not AvailabilityKind.LOCAL for item in result.alternatives)
    transfer = next(item for item in result.alternatives if item.kind is AvailabilityKind.TRANSFER)
    assert transfer.origin_id == "sede-centro"
    assert transfer.quantity == Decimal("80")
    assert transfer.source == "synthetic-ferreteria-demo-xeon"
    assert transfer.observed_at == "2026-10-08T12:00:00+00:00"
    delivery = next(item for item in result.alternatives if item.kind is AvailabilityKind.DELIVERY)
    assert delivery.origin_id == "origen-entrega-sintetica"
    assert delivery.quantity == Decimal("40")
    assert delivery.source == "synthetic-ferreteria-demo-xeon"
    assert delivery.observed_at == "2026-10-08T12:00:00+00:00"
    alternative_total = sum((item.quantity for item in result.alternatives), Decimal("0"))
    assert alternative_total != result.shortfall
    assert result.local_available + alternative_total != result.requested_quantity


def test_sufficient_local_stock_keeps_unreserved_alternatives() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-centro",
            requested_quantity="50",
            evaluated_at=EVALUATED_AT,
        )
    )

    assert result.fulfillment_status is FulfillmentStatus.SUFFICIENT
    assert result.local_available == Decimal("80")
    assert result.shortfall == Decimal("0")
    assert result.requested_quantity == Decimal("50")
    assert AvailabilityKind.LOCAL in {item.kind for item in result.items}
    assert all(item.kind is not AvailabilityKind.LOCAL for item in result.alternatives)


def test_missing_snapshots_stay_unknown_not_depleted() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="SKU-INEXISTENTE",
            requested_branch_id="sede-centro",
            requested_quantity="10",
            evaluated_at=EVALUATED_AT,
        )
    )

    assert result.fulfillment_status is FulfillmentStatus.UNKNOWN
    assert result.fulfillment_status is not FulfillmentStatus.PARTIAL
    assert result.local_available is None
    assert result.shortfall is None
    assert result.items == ()
    assert result.alternatives == ()


def test_unobserved_local_branch_stays_unknown_with_verified_alternatives() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="TUB-PVC-20",
            requested_branch_id="sede-centro",
            requested_quantity="10",
            evaluated_at=EVALUATED_AT,
        )
    )

    assert result.fulfillment_status is FulfillmentStatus.UNKNOWN
    assert result.local_available is None
    assert result.shortfall is None
    assert all(item.kind is not AvailabilityKind.LOCAL for item in result.items)
    transfer = next(item for item in result.alternatives if item.kind is AvailabilityKind.TRANSFER)
    assert transfer.origin_id == "sede-norte"
    assert transfer.quantity == Decimal("12")
    assert transfer.source == "synthetic-ferreteria-demo-xeon"
    assert transfer.observed_at == "2026-10-08T12:00:00+00:00"


def test_fresh_local_snapshot_is_firm_and_explains_fulfillment() -> None:
    service = GetStockByBranches(
        InMemoryBranchInventory(
            (
                _snapshot(branch_id="sede-centro", quantity="80"),
                _snapshot(
                    branch_id="sede-norte",
                    origin_name="Ferreteria Demo XEON Norte",
                    quantity="20",
                ),
            )
        )
    )

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-centro",
            requested_quantity="50",
            evaluated_at=EVALUATED_AT,
        )
    )

    local = next(item for item in result.items if item.kind is AvailabilityKind.LOCAL)
    assert local.freshness is Freshness.FRESH
    assert local.is_firm is True
    assert local.valid_until == VALID_UNTIL
    assert local.age == "PT3H"
    assert result.fulfillment_status is FulfillmentStatus.SUFFICIENT
    assert result.local_available == Decimal("80")


def test_expired_local_snapshot_keeps_evidence_and_is_not_firm() -> None:
    service = GetStockByBranches(
        InMemoryBranchInventory((_snapshot(branch_id="sede-norte", quantity="20"),))
    )

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-norte",
            requested_quantity="50",
            evaluated_at=EVALUATED_AFTER_EXPIRY,
        )
    )

    local = next(item for item in result.items if item.kind is AvailabilityKind.LOCAL)
    assert local.origin_id == "sede-norte"
    assert local.quantity == Decimal("20")
    assert local.source == "synthetic-ferreteria-demo-xeon"
    assert local.observed_at == OBSERVED_AT
    assert local.valid_until == VALID_UNTIL
    assert local.freshness is Freshness.STALE
    assert local.is_firm is False
    assert local.age == "PT24H"
    assert result.fulfillment_status is FulfillmentStatus.UNKNOWN
    assert result.fulfillment_status is not FulfillmentStatus.PARTIAL
    assert result.local_available is None
    assert result.shortfall is None


def test_snapshot_without_validity_is_unknown_and_not_firm() -> None:
    service = GetStockByBranches(
        InMemoryBranchInventory(
            (_snapshot(branch_id="sede-centro", quantity="80", valid_until=None),)
        )
    )

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-centro",
            requested_quantity="50",
            evaluated_at=EVALUATED_AT,
        )
    )

    local = next(item for item in result.items if item.kind is AvailabilityKind.LOCAL)
    assert local.valid_until is None
    assert local.freshness is Freshness.UNKNOWN
    assert local.is_firm is False
    assert local.age == "PT3H"
    assert result.fulfillment_status is FulfillmentStatus.UNKNOWN
    assert result.local_available is None
    assert result.shortfall is None
