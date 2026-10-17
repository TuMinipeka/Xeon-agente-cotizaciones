import asyncio
from decimal import Decimal

import httpx

from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.quote_draft import DraftLineRequest, QuoteDraftReady
from xeon.config import Settings


def test_hermes_search_resolves_semantic_and_specs_queries_with_db_prices() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    fencing = container.hermes_tools.search_products(
        "necesito algo para cercar ganado en un potrero"
    )
    assert fencing.status == "semantic_candidates"
    assert fencing.candidates[0].sku == "ALA-14"
    assert fencing.candidates[0].unit_price == "1850.00"
    assert fencing.candidates[0].specs["calibre"] == "14"

    pipe = container.hermes_tools.search_products("tuberia para agua fria de 200 psi")
    assert pipe.status == "semantic_candidates"
    assert pipe.candidates[0].sku == "TUB-PVC-20"
    assert pipe.candidates[0].unit_price == "4200.00"
    assert pipe.candidates[0].specs["presion_psi"] == "200"


def test_hermes_search_requires_clarification_on_ambiguous_or_unitless_input() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    ambiguous = container.hermes_tools.search_products("el coso del aire")
    assert ambiguous.status == "clarification_required"
    assert ambiguous.clarification_reason == "ambiguous_reference"

    unitless = container.hermes_tools.search_products("la pieza mide 20 x 30 x 10")
    assert unitless.status == "clarification_required"
    assert unitless.clarification_reason == "missing_units"


def test_hermes_tools_delegate_pricing_and_stock_to_deterministic_backend() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    draft_result = container.hermes_tools.create_quote_draft(
        tenant_id="demo",
        request_id="hermes-req-1",
        lines=(DraftLineRequest(query="CEM-50", quantity=Decimal("10")),),
    )
    assert isinstance(draft_result, QuoteDraftReady)
    assert str(draft_result.quote.total.amount) == "289000.00"

    stock_result = container.hermes_tools.get_stock_by_branches(
        sku="CEM-50",
        requested_branch_id="sede-norte",
        evaluated_at="2026-10-08T15:00:00+00:00",
        requested_quantity=Decimal("50"),
    )
    assert stock_result.sku == "CEM-50"
    assert stock_result.local_available == Decimal("20")
    assert stock_result.shortfall == Decimal("30")


def test_chat_endpoint_surfaces_hermes_verified_candidates() -> None:
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

