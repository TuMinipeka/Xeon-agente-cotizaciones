from decimal import Decimal

import pytest

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.application.quote_draft import (
    CatalogUnavailable,
    ClarificationRequired,
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    DiscountPolicyUnavailable,
    DraftLineRequest,
    GetQuoteDraft,
    ProductNotFound,
    QuoteDraftReady,
    QuoteNotFoundError,
)
from xeon.domain.money import Money
from xeon.domain.quote import INITIAL_QUOTE_VERSION, InvalidQuantityError, QuoteStatus


def _service(
    catalog: InMemoryProductCatalog | None = None,
) -> tuple[CreateQuoteDraft, GetQuoteDraft, InMemoryQuoteDraftRepository]:
    quotes = InMemoryQuoteDraftRepository()
    catalog = catalog or InMemoryProductCatalog()
    return CreateQuoteDraft(catalog, quotes), GetQuoteDraft(quotes), quotes


def _command(
    *lines: DraftLineRequest,
    tenant_id: str = "demo",
    request_id: str = "req-1",
    discount_requested: bool = False,
) -> CreateQuoteDraftCommand:
    return CreateQuoteDraftCommand(
        tenant_id=tenant_id,
        request_id=request_id,
        lines=lines,
        discount_requested=discount_requested,
    )


def test_sku_and_quantity_create_exact_draft() -> None:
    service, getter, quotes = _service()

    result = service.execute(
        _command(DraftLineRequest("CEM-50", 50), DraftLineRequest("ALA-14", 300))
    )

    assert isinstance(result, QuoteDraftReady)
    draft = result.quote
    assert result.replayed is False
    assert draft.status is QuoteStatus.DRAFT
    assert draft.version == INITIAL_QUOTE_VERSION
    assert draft.subtotal == draft.total == Money("2000000.00", "COP")
    assert draft.lines[0].line_total == Money("1445000.00", "COP")
    assert draft.lines[1].line_total == Money("555000.00", "COP")
    assert quotes.get(draft.id) is draft
    assert getter.execute(draft.id, "demo") is draft
    assert "sinteticos" in draft.notes.casefold()


def test_alias_lookup_does_not_change_list_price() -> None:
    service, _, _ = _service()

    result = service.execute(_command(DraftLineRequest("cemento", Decimal("2"))))

    assert isinstance(result, QuoteDraftReady)
    assert result.quote.lines[0].sku == "CEM-50"
    assert result.quote.lines[0].unit_price == Money("28900.00", "COP")
    assert result.quote.total == Money("57800.00", "COP")


def test_ambiguous_reference_requires_clarification() -> None:
    service, _, quotes = _service()

    result = service.execute(_command(DraftLineRequest("el coso del aire", 1)))

    assert isinstance(result, ClarificationRequired)
    assert result.reason == "ambiguous_reference"
    assert quotes.get_by_idempotency_key("demo", "req-1") is None


def test_measurements_without_units_require_clarification() -> None:
    service, _, _ = _service()

    result = service.execute(_command(DraftLineRequest("La pieza mide 20 x 30 x 10", 1)))

    assert isinstance(result, ClarificationRequired)
    assert result.reason == "missing_units"


def test_missing_sku_is_not_reported_as_sold_out() -> None:
    service, _, _ = _service()

    result = service.execute(_command(DraftLineRequest("SKU-INEXISTENTE", 10)))

    assert isinstance(result, ProductNotFound)
    assert "existencia cero" in result.message.casefold()


def test_zero_quantity_is_rejected_before_pricing() -> None:
    service, _, _ = _service()

    with pytest.raises(InvalidQuantityError):
        service.execute(_command(DraftLineRequest("CEM-50", 0)))


def test_unavailable_catalog_is_not_reported_as_sold_out() -> None:
    catalog = InMemoryProductCatalog()
    catalog.mark_unavailable()
    service, _, _ = _service(catalog)

    result = service.execute(_command(DraftLineRequest("CEM-50", 1)))

    assert isinstance(result, CatalogUnavailable)
    assert "no se puede confirmar existencia" in result.message.casefold()


def test_requested_discount_does_not_invent_policy() -> None:
    service, _, quotes = _service()

    result = service.execute(_command(DraftLineRequest("CEM-50", 1), discount_requested=True))

    assert isinstance(result, DiscountPolicyUnavailable)
    assert quotes.get_by_idempotency_key("demo", "req-1") is None


def test_same_idempotency_key_returns_same_draft() -> None:
    service, _, _ = _service()
    command = _command(DraftLineRequest("CEM-50", 2))

    first = service.execute(command)
    second = service.execute(command)

    assert isinstance(first, QuoteDraftReady)
    assert isinstance(second, QuoteDraftReady)
    assert first.replayed is False
    assert second.replayed is True
    assert second.quote.id == first.quote.id
    assert second.quote.total == first.quote.total


def test_get_draft_rejects_other_tenant() -> None:
    service, getter, _ = _service()
    result = service.execute(_command(DraftLineRequest("CEM-50", 1)))
    assert isinstance(result, QuoteDraftReady)

    with pytest.raises(QuoteNotFoundError):
        getter.execute(result.quote.id, "otro-tenant")
