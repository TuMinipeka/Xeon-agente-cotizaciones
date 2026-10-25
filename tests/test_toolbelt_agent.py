import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from xeon.agent.toolbelt import _extract_requested_branch, _extract_requested_quantity
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.quote_draft import DraftLineRequest, QuoteDraftReady
from xeon.config import Settings


def test_colombian_quantities_and_branch_word_boundaries() -> None:
    assert _extract_requested_quantity("quiero 1.000 bultos") == Decimal(1000)
    assert _extract_requested_quantity("quiero 1.500 bultos") == Decimal(1500)
    assert _extract_requested_quantity("quiero 2,5 metros") == Decimal("2.5")
    assert _extract_requested_quantity("quiero 2.5 metros") == Decimal("2.5")
    assert _extract_requested_branch("surtido en sede norte") == "sede-norte"
    assert _extract_requested_branch("entrega en sede sur") == "sede-sur"


def test_injected_clock_controls_stock_freshness() -> None:
    settings = Settings(llm_provider="mock", _env_file=None)
    fresh = build_container(settings, clock=lambda: datetime(2026, 10, 8, 15, 0, tzinfo=UTC))
    stale = build_container(settings, clock=lambda: datetime(2026, 10, 24, 15, 0, tzinfo=UTC))
    fresh_context, _, _, _ = fresh.commercial_tools.prepare_verified_context("10 bultos de cemento")
    stale_context, _, _, _ = stale.commercial_tools.prepare_verified_context("10 bultos de cemento")
    assert fresh_context is not None and "vigencia=fresh" in fresh_context
    assert stale_context is not None and "vigencia=stale" in stale_context


def test_quote_failure_is_visible_without_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private detail")

    monkeypatch.setattr(container.create_quote_draft, "execute", fail)
    context, _, _, _ = container.commercial_tools.prepare_verified_context("10 bultos de cemento")
    assert context is not None and "status=quote_unavailable" in context
    assert "private detail" not in context


def test_commercial_search_resolves_semantic_and_specs_queries_with_db_prices() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    fencing = container.commercial_tools.search_products(
        "necesito algo para cercar ganado en un potrero"
    )
    assert fencing.status == "semantic_candidates"
    assert fencing.candidates[0].sku == "ALA-14"
    assert fencing.candidates[0].unit_price == "1850.00"
    assert fencing.candidates[0].specs["calibre"] == "14"

    pipe = container.commercial_tools.search_products("tuberia para agua fria de 200 psi")
    assert pipe.status == "semantic_candidates"
    assert pipe.candidates[0].sku == "TUB-PVC-20"
    assert pipe.candidates[0].unit_price == "4200.00"
    assert pipe.candidates[0].specs["presion_psi"] == "200"


def test_plural_tubos_keeps_core_product_in_first_three_candidates() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    outcome = container.commercial_tools.search_products("necesito 10 tubos pvc")

    assert outcome.status == "semantic_candidates"
    assert outcome.candidates[0].sku == "TUB-PVC-20"
    assert outcome.candidates[0].unit_price == "4200.00"
    assert len(outcome.candidates) == 3


def test_commercial_search_requires_clarification_on_ambiguous_or_unitless_input() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    ambiguous = container.commercial_tools.search_products("el coso del aire")
    assert ambiguous.status == "clarification_required"
    assert ambiguous.clarification_reason == "ambiguous_reference"

    unitless = container.commercial_tools.search_products("la pieza mide 20 x 30 x 10")
    assert unitless.status == "clarification_required"
    assert unitless.clarification_reason == "missing_units"


def test_commercial_tools_delegate_pricing_and_stock_to_deterministic_backend() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    draft_result = container.commercial_tools.create_quote_draft(
        tenant_id="demo",
        request_id="xeon-req-1",
        lines=(DraftLineRequest(query="CEM-50", quantity=Decimal("10")),),
    )
    assert isinstance(draft_result, QuoteDraftReady)
    assert str(draft_result.quote.total.amount) == "289000.00"

    stock_result = container.commercial_tools.get_stock_by_branches(
        sku="CEM-50",
        requested_branch_id="sede-norte",
        evaluated_at="2026-10-08T15:00:00+00:00",
        requested_quantity=Decimal("50"),
    )
    assert stock_result.sku == "CEM-50"
    assert stock_result.local_available == Decimal("20")
    assert stock_result.shortfall == Decimal("30")


def test_chat_endpoint_surfaces_verified_candidates() -> None:
    async def run() -> httpx.Response:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/chat",
                json={"message": "busco material para fundir placa y pegar ladrillo"},
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "CEM-50" in reply
    assert "28900.00" in reply
