from __future__ import annotations

from typing import Protocol

from xeon.domain.inventory import StockSnapshot


class BranchInventory(Protocol):
    def list_snapshots(self, sku: str) -> tuple[StockSnapshot, ...]:
        """Return observed snapshots for a SKU. Never invents quantities."""
