from datetime import UTC, datetime, timedelta

from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.catalog.synthetic_seed import (
    SYNTHETIC_CATALOG_SIZE,
    SYNTHETIC_PRODUCTS,
    SYNTHETIC_SOURCE,
)
from xeon.adapters.inventory.memory import InMemoryBranchInventory
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.agent.hermes import HermesToolbelt
from xeon.application.quote_draft import CreateQuoteDraft
from xeon.application.stock import GetStockByBranches


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 17, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _tools(clock: MutableClock | None = None) -> HermesToolbelt:
    catalog = InMemoryProductCatalog()
    quotes = InMemoryQuoteDraftRepository()
    return HermesToolbelt(
        catalog=catalog,
        create_quote_draft=CreateQuoteDraft(catalog, quotes),
        get_stock_by_branches=GetStockByBranches(InMemoryBranchInventory()),
        clock=clock,
    )


def _reply(tools: HermesToolbelt, message: str, conversation: str = "cart") -> str:
    prepared = tools.prepare_customer_turn(message, conversation_id=conversation)
    assert prepared is not None
    return prepared.customer_reply


def _cart_with_cement(tools: HermesToolbelt, conversation: str = "cart") -> None:
    assert "ciudad o zona" in _reply(tools, "cemento", conversation)
    assert "bultos necesitas" in _reply(tools, "zona centro", conversation)
    assert "2 bultos" in _reply(tools, "2 bultos", conversation)


def _ascii(value: str) -> str:
    return value.encode("ascii", "ignore").decode()


def test_synthetic_seed_contains_exactly_two_thousand_tagged_references() -> None:
    assert len(SYNTHETIC_PRODUCTS) == SYNTHETIC_CATALOG_SIZE == 2_000
    assert all(product.source == SYNTHETIC_SOURCE for product in SYNTHETIC_PRODUCTS)
    assert any(product.sku == "LAM-ZIN-28-244" for product in SYNTHETIC_PRODUCTS)


def test_cart_collects_multiple_products_and_creates_one_draft_at_finish() -> None:
    tools = _tools()
    _cart_with_cement(tools)

    assert "metros necesitas" in _reply(tools, "alambre")
    assert "20 metros" in _reply(tools, "20 metros")
    summary = _reply(tools, "que llevo")
    assert "2 bultos" in summary
    assert "20 metros" in summary
    assert "Total provisional" in summary

    final = _reply(tools, "finalizar")
    assert "borrador con 2 productos" in final
    assert "COP" not in final
    assert "SKU" not in final


def test_cart_allows_quantity_change_and_product_removal() -> None:
    tools = _tools()
    _cart_with_cement(tools)
    _reply(tools, "alambre")
    _reply(tools, "20 metros")

    changed = _reply(tools, "cambia cemento a 3 bultos")
    removed = _reply(tools, "quita alambre")
    summary = _reply(tools, "que llevo")

    assert "3 bultos" in changed
    assert "Alambre" in removed
    assert "3 bultos" in summary
    assert "Alambre" not in summary


def test_inactive_cart_asks_between_one_and_three_days_then_starts_new() -> None:
    clock = MutableClock()
    tools = _tools(clock)
    _cart_with_cement(tools, "timed")

    clock.now += timedelta(hours=25)
    resume = _reply(tools, "martillo", "timed")
    assert "anterior" in resume

    _reply(tools, "continuar", "timed")
    clock.now += timedelta(days=4)
    new_quote = _reply(tools, "alambre", "timed")
    assert "cotizacion anterior" not in _ascii(new_quote)
    assert "metros necesitas" in new_quote


def test_finalized_draft_asks_whether_to_reuse_or_start_new() -> None:
    tools = _tools()
    _cart_with_cement(tools, "finalized")
    _reply(tools, "finalizar", "finalized")

    choice = _reply(tools, "martillo", "finalized")
    assert "anterior" in choice
    continued = _reply(tools, "a la misma", "finalized")
    assert "Martillo" in continued
    assert "Cemento" not in continued
