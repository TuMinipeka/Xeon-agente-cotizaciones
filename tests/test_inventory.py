from decimal import Decimal

import pytest

from xeon.domain.inventory import (
    AvailabilityKind,
    Freshness,
    FulfillmentStatus,
    InvalidInventoryError,
    StockChannel,
    StockSnapshot,
    assess_freshness,
    classify_availability,
    classify_freshness,
    explain_local_fulfillment,
)

OBSERVED_AT = "2026-10-08T12:00:00+00:00"
VALID_UNTIL = "2026-10-08T18:00:00+00:00"
EVALUATED_WHILE_VALID = "2026-10-08T15:00:00+00:00"
EVALUATED_AFTER_EXPIRY = "2026-10-09T12:00:00+00:00"


def _on_hand(*, branch_id: str, quantity: str, valid_until: str | None = None) -> StockSnapshot:
    return StockSnapshot(
        sku="TUB-PVC-20",
        branch_id=branch_id,
        origin_id=branch_id,
        origin_name=f"Ferreteria Demo XEON {branch_id.removeprefix('sede-').title()}",
        quantity=Decimal(quantity),
        channel=StockChannel.ON_HAND,
        source="synthetic-ferreteria-demo-xeon",
        observed_at=OBSERVED_AT,
        valid_until=valid_until,
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


def test_local_shortfall_is_exact_when_requested_exceeds_on_hand() -> None:
    result = explain_local_fulfillment(local_quantity=Decimal("20"), requested_quantity="50")

    assert result.status is FulfillmentStatus.PARTIAL
    assert result.local_available == Decimal("20")
    assert result.shortfall == Decimal("30")


def test_local_stock_covering_request_is_sufficient() -> None:
    result = explain_local_fulfillment(local_quantity=Decimal("80"), requested_quantity="50")

    assert result.status is FulfillmentStatus.SUFFICIENT
    assert result.local_available == Decimal("80")
    assert result.shortfall == Decimal("0")


def test_missing_local_snapshot_stays_unknown_not_depleted() -> None:
    result = explain_local_fulfillment(local_quantity=None, requested_quantity="10")

    assert result.status is FulfillmentStatus.UNKNOWN
    assert result.status is not FulfillmentStatus.PARTIAL
    assert result.local_available is None
    assert result.shortfall is None


def test_observed_zero_is_partial_not_unknown() -> None:
    result = explain_local_fulfillment(local_quantity=Decimal("0"), requested_quantity="10")

    assert result.status is FulfillmentStatus.PARTIAL
    assert result.local_available == Decimal("0")
    assert result.shortfall == Decimal("10")


def test_requested_quantity_must_be_positive() -> None:
    with pytest.raises(InvalidInventoryError, match="mayor que cero"):
        explain_local_fulfillment(local_quantity=Decimal("8"), requested_quantity="0")


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


def test_snapshot_with_source_validity_is_fresh_at_injected_instant() -> None:
    snapshot = _on_hand(branch_id="sede-centro", quantity="50", valid_until=VALID_UNTIL)

    freshness = classify_freshness(snapshot, evaluated_at=EVALUATED_WHILE_VALID)
    assessment = assess_freshness(snapshot, evaluated_at=EVALUATED_WHILE_VALID)

    assert freshness is Freshness.FRESH
    assert assessment.freshness is Freshness.FRESH
    assert assessment.is_firm is True
    assert assessment.age == "PT3H"
    assert snapshot.valid_until == VALID_UNTIL
    assert snapshot.observed_at == OBSERVED_AT
    assert snapshot.origin_id == "sede-centro"
    assert snapshot.quantity == Decimal("50")
    assert snapshot.source == "synthetic-ferreteria-demo-xeon"


def test_expired_snapshot_is_stale_keeps_evidence_and_is_not_firm() -> None:
    snapshot = _on_hand(branch_id="sede-norte", quantity="20", valid_until=VALID_UNTIL)

    freshness = classify_freshness(snapshot, evaluated_at=EVALUATED_AFTER_EXPIRY)
    assessment = assess_freshness(snapshot, evaluated_at=EVALUATED_AFTER_EXPIRY)

    assert freshness is Freshness.STALE
    assert assessment.freshness is Freshness.STALE
    assert assessment.is_firm is False
    assert assessment.age == "PT24H"
    assert snapshot.origin_id == "sede-norte"
    assert snapshot.origin_name == "Ferreteria Demo XEON Norte"
    assert snapshot.quantity == Decimal("20")
    assert snapshot.source == "synthetic-ferreteria-demo-xeon"
    assert snapshot.observed_at == OBSERVED_AT
    assert snapshot.valid_until == VALID_UNTIL


def test_snapshot_without_valid_until_is_unknown_not_firm() -> None:
    snapshot = _on_hand(branch_id="sede-centro", quantity="50")

    freshness = classify_freshness(snapshot, evaluated_at=EVALUATED_WHILE_VALID)
    assessment = assess_freshness(snapshot, evaluated_at=EVALUATED_WHILE_VALID)

    assert snapshot.valid_until is None
    assert freshness is Freshness.UNKNOWN
    assert assessment.freshness is Freshness.UNKNOWN
    assert assessment.is_firm is False
    assert assessment.age == "PT3H"
    assert snapshot.quantity == Decimal("50")
    assert snapshot.observed_at == OBSERVED_AT


def test_validity_at_exact_valid_until_instant_stays_fresh() -> None:
    snapshot = _on_hand(branch_id="sede-centro", quantity="12", valid_until=VALID_UNTIL)

    assert classify_freshness(snapshot, evaluated_at=VALID_UNTIL) is Freshness.FRESH
    assert assess_freshness(snapshot, evaluated_at=VALID_UNTIL).is_firm is True


def test_expired_local_quantity_stays_unknown_not_zero() -> None:
    result = explain_local_fulfillment(
        local_quantity=Decimal("80"),
        requested_quantity="50",
        freshness=Freshness.STALE,
    )

    assert result.status is FulfillmentStatus.UNKNOWN
    assert result.status is not FulfillmentStatus.SUFFICIENT
    assert result.status is not FulfillmentStatus.PARTIAL
    assert result.local_available is None
    assert result.shortfall is None


def test_unknown_freshness_local_quantity_stays_unknown_not_zero() -> None:
    result = explain_local_fulfillment(
        local_quantity=Decimal("20"),
        requested_quantity="50",
        freshness=Freshness.UNKNOWN,
    )

    assert result.status is FulfillmentStatus.UNKNOWN
    assert result.local_available is None
    assert result.shortfall is None
