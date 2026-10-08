from decimal import Decimal

import pytest

from xeon.domain.inventory import (
    AvailabilityKind,
    InvalidInventoryError,
    StockChannel,
    StockSnapshot,
    classify_availability,
)


def _on_hand(*, branch_id: str, quantity: str) -> StockSnapshot:
    return StockSnapshot(
        sku="TUB-PVC-20",
        branch_id=branch_id,
        origin_id=branch_id,
        origin_name=f"Ferreteria Demo XEON {branch_id.removeprefix('sede-').title()}",
        quantity=Decimal(quantity),
        channel=StockChannel.ON_HAND,
        source="synthetic-ferreteria-demo-xeon",
        observed_at="2026-10-08T12:00:00+00:00",
    )


def test_alternative_branch_stock_is_not_classified_as_local() -> None:
    snapshot = _on_hand(branch_id="sede-norte", quantity="8")

    kind = classify_availability(snapshot, requested_branch_id="sede-centro")

    assert kind is AvailabilityKind.TRANSFER
    assert kind is not AvailabilityKind.LOCAL


def test_requested_branch_on_hand_is_local_and_keeps_origin() -> None:
    snapshot = _on_hand(branch_id="sede-centro", quantity="50")

    kind = classify_availability(snapshot, requested_branch_id="sede-centro")

    assert kind is AvailabilityKind.LOCAL
    assert snapshot.origin_id == "sede-centro"


def test_delivery_snapshot_is_not_local_stock() -> None:
    snapshot = StockSnapshot(
        sku="ALA-14",
        branch_id=None,
        origin_id="origen-entrega-sintetica",
        origin_name="Entrega sintetica Ferreteria Demo XEON",
        quantity=Decimal("100"),
        channel=StockChannel.DELIVERY,
        source="synthetic-ferreteria-demo-xeon",
        observed_at="2026-10-08T12:00:00+00:00",
    )

    kind = classify_availability(snapshot, requested_branch_id="sede-centro")

    assert kind is AvailabilityKind.DELIVERY
    assert kind is not AvailabilityKind.LOCAL
    assert snapshot.origin_id == "origen-entrega-sintetica"


def test_on_hand_snapshot_requires_branch() -> None:
    with pytest.raises(InvalidInventoryError, match="sede"):
        StockSnapshot(
            sku="CEM-50",
            branch_id=None,
            origin_id="sede-centro",
            origin_name="Ferreteria Demo XEON Centro",
            quantity=Decimal("1"),
            channel=StockChannel.ON_HAND,
            source="synthetic-ferreteria-demo-xeon",
            observed_at="2026-10-08T12:00:00+00:00",
        )
