from decimal import Decimal

from xeon.adapters.inventory.memory import InMemoryBranchInventory
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery
from xeon.domain.inventory import AvailabilityKind, FulfillmentStatus


def test_alternative_branch_is_not_reported_as_local_stock() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(sku="TUB-PVC-20", requested_branch_id="sede-centro")
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
        GetStockByBranchesQuery(sku="CEM-50", requested_branch_id="sede-centro")
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
        GetStockByBranchesQuery(sku="SKU-INEXISTENTE", requested_branch_id="sede-centro")
    )

    assert result.items == ()


def test_partial_local_stock_reports_exact_shortfall_and_unreserved_alternatives() -> None:
    service = GetStockByBranches(InMemoryBranchInventory())

    result = service.execute(
        GetStockByBranchesQuery(
            sku="CEM-50",
            requested_branch_id="sede-norte",
            requested_quantity="50",
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
