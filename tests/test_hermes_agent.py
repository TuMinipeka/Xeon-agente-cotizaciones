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


def test_chat_endpoint_asks_location_before_catalog_selection() -> None:
    async def run() -> tuple[httpx.Response, httpx.Response]:
        settings = Settings(llm_provider="mock", _env_file=None)
        transport = httpx.ASGITransport(app=create_app(settings=settings))
        conversation_id = "55555555-5555-5555-5555-555555555555"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/v1/chat",
                json={
                    "conversation_id": conversation_id,
                    "message": "busco material para fundir placa y pegar ladrillo",
                },
            )
            second = await client.post(
                "/v1/chat",
                json={"conversation_id": conversation_id, "message": "zona centro"},
            )
        return first, second

    first, second = asyncio.run(run())

    assert "ciudad o zona" in first.json()["reply"]
    reply = second.json()["reply"]
    assert "Cemento gris 50 kg" in reply
    assert "$28.900" in reply
    assert "COP" not in reply
    assert "CEM-50" not in reply


def test_multiple_semantic_candidates_require_natural_selection_before_cart() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))
    tools = container.hermes_tools

    location = tools.prepare_customer_turn(
        "necesito 10 laminas de zinc para una casa",
        conversation_id="conversation-confirmation",
    )
    candidates = tools.prepare_customer_turn(
        "zona centro",
        conversation_id="conversation-confirmation",
    )
    selected = tools.prepare_customer_turn(
        "la primera opcion",
        conversation_id="conversation-confirmation",
    )

    assert location is not None and "ciudad o zona" in location.customer_reply
    assert candidates is not None
    assert "Lamina de zinc calibre 28" in candidates.customer_reply
    assert "LAM-ZIN" not in candidates.customer_reply
    assert "create_quote_draft" not in (candidates.verified_context or "")
    assert selected is not None
    assert "10 laminas" in selected.customer_reply
    assert "create_quote_draft" not in (selected.verified_context or "")


def test_pending_selection_is_replaced_by_clear_new_product_intent() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))
    tools = container.hermes_tools
    conversation = "intent-change"

    tools.prepare_customer_turn("necesito laminas de zinc", conversation_id=conversation)
    tools.prepare_customer_turn("zona sur", conversation_id=conversation)
    changed = tools.prepare_customer_turn(
        "mejor necesito 2 bultos de cemento",
        conversation_id=conversation,
    )

    assert changed is not None
    assert "Cemento gris 50 kg" in changed.customer_reply
    assert "Lamina" not in changed.customer_reply
    selected = tools.prepare_customer_turn(
        "la primera opcion",
        conversation_id=conversation,
    )
    assert selected is not None
    assert "2 bultos" in selected.customer_reply


def test_hermes_provider_builds_local_api_bridge_with_temporary_model() -> None:
    settings = Settings(
        llm_provider="hermes",
        hermes_base_url="http://127.0.0.1:8642/v1",
        hermes_model="gpt-5.6-luna",
        _env_file=None,
    )
    container = build_container(settings)
    try:
        assert (
            settings.resolve_hermes_api_key().get_secret_value() == "xeon-hermes-local-bridge-2026"
        )
        assert container.settings.hermes_model == "gpt-5.6-luna"
    finally:
        asyncio.run(container.aclose())
