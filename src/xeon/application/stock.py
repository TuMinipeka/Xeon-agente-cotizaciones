from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from xeon.application.ports.inventory import BranchInventory
from xeon.domain.inventory import (
    AvailabilityKind,
    InvalidInventoryError,
    StockChannel,
    StockSnapshot,
    classify_availability,
)


@dataclass(frozen=True, slots=True)
class GetStockByBranchesQuery:
    sku: str
    requested_branch_id: str


@dataclass(frozen=True, slots=True)
class AvailabilityItem:
    sku: str
    branch_id: str | None
    origin_id: str
    origin_name: str
    quantity: Decimal
    kind: AvailabilityKind
    channel: StockChannel
    source: str
    observed_at: str


@dataclass(frozen=True, slots=True)
class StockByBranches:
    sku: str
    requested_branch_id: str
    items: tuple[AvailabilityItem, ...]


def _item_from_snapshot(snapshot: StockSnapshot, *, requested_branch_id: str) -> AvailabilityItem:
    return AvailabilityItem(
        sku=snapshot.sku,
        branch_id=snapshot.branch_id,
        origin_id=snapshot.origin_id,
        origin_name=snapshot.origin_name,
        quantity=snapshot.quantity,
        kind=classify_availability(snapshot, requested_branch_id=requested_branch_id),
        channel=snapshot.channel,
        source=snapshot.source,
        observed_at=snapshot.observed_at,
    )


class GetStockByBranches:
    def __init__(self, inventory: BranchInventory) -> None:
        self._inventory = inventory

    def execute(self, query: GetStockByBranchesQuery) -> StockByBranches:
        sku = query.sku.strip().upper()
        requested_branch_id = query.requested_branch_id.strip()
        if not sku:
            raise InvalidInventoryError("sku es obligatorio.")
        if not requested_branch_id:
            raise InvalidInventoryError("requested_branch_id es obligatorio.")
        items = tuple(
            _item_from_snapshot(snapshot, requested_branch_id=requested_branch_id)
            for snapshot in self._inventory.list_snapshots(sku)
        )
        return StockByBranches(sku=sku, requested_branch_id=requested_branch_id, items=items)
