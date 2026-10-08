from decimal import Decimal

from xeon.adapters.inventory.memory import InMemoryBranchInventory
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery
from xeon.domain.inventory import AvailabilityKind


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
