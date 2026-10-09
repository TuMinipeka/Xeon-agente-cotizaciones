from __future__ import annotations

from decimal import Decimal

from xeon.domain.inventory import StockChannel, StockSnapshot

SYNTHETIC_INVENTORY_SOURCE = "synthetic-ferreteria-demo-xeon"
SYNTHETIC_OBSERVED_AT = "2026-10-08T12:00:00+00:00"
SYNTHETIC_VALID_UNTIL = "2026-10-08T18:00:00+00:00"
SYNTHETIC_DELIVERY_ORIGIN_ID = "origen-entrega-sintetica"
SYNTHETIC_DELIVERY_ORIGIN_NAME = "Entrega sintetica Ferreteria Demo XEON"


def _on_hand(
    sku: str,
    branch_id: str,
    origin_name: str,
    quantity: str,
    *,
    valid_until: str | None = SYNTHETIC_VALID_UNTIL,
) -> StockSnapshot:
    return StockSnapshot(
        sku=sku,
        branch_id=branch_id,
        origin_id=branch_id,
        origin_name=origin_name,
        quantity=Decimal(quantity),
        channel=StockChannel.ON_HAND,
        source=SYNTHETIC_INVENTORY_SOURCE,
        observed_at=SYNTHETIC_OBSERVED_AT,
        valid_until=valid_until,
    )


def _delivery(sku: str, quantity: str) -> StockSnapshot:
    return StockSnapshot(
        sku=sku,
        branch_id=None,
        origin_id=SYNTHETIC_DELIVERY_ORIGIN_ID,
        origin_name=SYNTHETIC_DELIVERY_ORIGIN_NAME,
        quantity=Decimal(quantity),
        channel=StockChannel.DELIVERY,
        source=SYNTHETIC_INVENTORY_SOURCE,
        observed_at=SYNTHETIC_OBSERVED_AT,
        valid_until=SYNTHETIC_VALID_UNTIL,
    )


SYNTHETIC_SNAPSHOTS: tuple[StockSnapshot, ...] = (
    _on_hand("CEM-50", "sede-centro", "Ferreteria Demo XEON Centro", "80"),
    _on_hand("CEM-50", "sede-norte", "Ferreteria Demo XEON Norte", "20"),
    _delivery("CEM-50", "40"),
    _on_hand("TUB-PVC-20", "sede-norte", "Ferreteria Demo XEON Norte", "12"),
    _on_hand("ALA-14", "sede-sur", "Ferreteria Demo XEON Sur", "300", valid_until=None),
)


class InMemoryBranchInventory:
    """Observed synthetic snapshots by SKU. Never invents missing branches or quantities."""

    def __init__(self, snapshots: tuple[StockSnapshot, ...] = SYNTHETIC_SNAPSHOTS) -> None:
        index: dict[str, list[StockSnapshot]] = {}
        for snapshot in snapshots:
            index.setdefault(snapshot.sku, []).append(snapshot)
        self._index = {sku: tuple(items) for sku, items in index.items()}

    def list_snapshots(self, sku: str) -> tuple[StockSnapshot, ...]:
        needle = sku.strip().upper()
        if not needle:
            return ()
        return self._index.get(needle, ())
