from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from xeon.adapters.sql.connection import SqlReader, mapped
from xeon.connectors.schema import ConnectorConfig
from xeon.domain.inventory import StockChannel, StockSnapshot


def _instant(value: Any, timezone: str | None) -> str:
    """Render a DB instant; a naive one gets the declared zone, otherwise stays naive."""
    if timezone is not None:
        parsed = value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.strip())
            except ValueError:
                return value
        if isinstance(parsed, datetime) and parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo(timezone)).isoformat()
    return str(value)


class SqlBranchInventory:
    def __init__(self, reader: SqlReader, config: ConnectorConfig) -> None:
        self._reader = reader
        self._config = config

    def list_snapshots(self, sku: str) -> tuple[StockSnapshot, ...]:
        query = self._config.stock_by_sku
        snapshots = []
        for row in self._reader.rows(query, sku=sku):
            branch_id = str(mapped(row, query, "branch_id"))
            zone = self._config.naive_datetime_timezone
            observed = mapped(row, query, "observed_at") or datetime.now(UTC).isoformat()
            valid_until = mapped(row, query, "valid_until")
            snapshots.append(
                StockSnapshot(
                    sku=sku,
                    branch_id=branch_id,
                    origin_id=branch_id,
                    origin_name=str(mapped(row, query, "branch_name", branch_id)),
                    quantity=Decimal(str(mapped(row, query, "quantity"))),
                    channel=StockChannel.ON_HAND,
                    source="sql-connector",
                    observed_at=_instant(observed, zone),
                    valid_until=_instant(valid_until, zone) if valid_until is not None else None,
                )
            )
        return tuple(snapshots)
