from decimal import Decimal

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.inventory.memory import InMemoryBranchInventory
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.application.commercial_turn import (
    SYNTHETIC_CHAT_EVALUATED_AT,
    CommercialTurn,
    extract_requested_lines,
)
from xeon.application.find_product import FindProduct, ProductFound
from xeon.application.quote_draft import (
    ClarificationRequired,
    CreateQuoteDraft,
    DraftLineRequest,
    QuoteDraftReady,
)
from xeon.application.stock import GetStockByBranches
from xeon.domain.quote import QuoteStatus


def test_extracts_cement_and_wire_lines_from_spanish_request() -> None:
    lines = extract_requested_lines("necesito 50 bultos de cemento y 300 metros de alambre")

    assert lines == (
        DraftLineRequest(query="cemento", quantity="50"),
        DraftLineRequest(query="alambre", quantity="300"),
    )


def test_find_product_resolves_alias_without_inventing_sku() -> None:
    result = FindProduct(InMemoryProductCatalog()).execute("cemento")

    assert isinstance(result, ProductFound)
    assert result.product.sku == "CEM-50"
    assert str(result.product.list_price.amount) == "28900.00"


def _turn() -> CommercialTurn:
    catalog = InMemoryProductCatalog()
    quotes = InMemoryQuoteDraftRepository()
    return CommercialTurn(
        find_product=FindProduct(catalog),
        get_stock=GetStockByBranches(InMemoryBranchInventory()),
        create_quote_draft=CreateQuoteDraft(catalog, quotes),
    )


def test_commercial_turn_runs_three_tools_and_creates_draft() -> None:
    result = _turn().execute(
        "necesito 50 bultos de cemento",
        tenant_id="demo",
        request_id="chat-req-1",
        requested_branch_id="sede-norte",
        evaluated_at=SYNTHETIC_CHAT_EVALUATED_AT,
    )

    assert result.tools_used == ("find_product", "consult_stock", "create_draft")
    assert result.outcome == "draft_ready"
    assert isinstance(result.quote_result, QuoteDraftReady)
    draft = result.quote_result.quote
    assert draft.status is QuoteStatus.DRAFT
    assert draft.lines[0].sku == "CEM-50"
    assert draft.lines[0].quantity == Decimal("50")
    assert str(draft.total.amount) == "1445000.00"
    assert result.stock is not None
    assert result.stock.sku == "CEM-50"
    assert result.stock.fulfillment_status is not None
    assert result.stock.fulfillment_status.value == "partial"


def test_ambiguous_chat_does_not_create_a_draft() -> None:
    result = _turn().execute(
        "necesito 1 coso del aire",
        tenant_id="demo",
        request_id="chat-req-2",
        requested_branch_id="sede-norte",
        evaluated_at=SYNTHETIC_CHAT_EVALUATED_AT,
    )

    assert result.tools_used == ("find_product",)
    assert result.outcome == "clarification_required"
    assert isinstance(result.quote_result, ClarificationRequired)
    assert result.quote is None
