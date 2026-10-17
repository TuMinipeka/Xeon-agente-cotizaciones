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
    assert "Cemento gris 50 kg" in reply
    assert "28,900.00" in reply
    assert "CEM-50" not in reply
    assert "SKU" not in reply
    assert "HERMES" not in reply


def test_semantic_candidate_requires_sku_confirmation_before_stock_or_draft() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    candidate_context = container.hermes_tools.format_verified_context(
        "necesito 50 bultos para fundir una placa y pegar ladrillo",
        conversation_id="conversation-confirmation",
    )

    assert candidate_context is not None
    assert "status=semantic_candidates" in candidate_context
    assert "SKU=CEM-50" in candidate_context
    assert "confirmation_required" in candidate_context
    assert "get_stock_by_branches" not in candidate_context
    assert "create_quote_draft" not in candidate_context

    rejected_context = container.hermes_tools.format_verified_context(
        "Confirmo el SKU ALA-14",
        conversation_id="conversation-confirmation",
    )

    assert rejected_context is not None
    assert "confirmation_required" in rejected_context
    assert "get_stock_by_branches" not in rejected_context
    assert "create_quote_draft" not in rejected_context

    confirmed_context = container.hermes_tools.format_verified_context(
        "Confirmo el SKU CEM-50",
        conversation_id="conversation-confirmation",
    )

    assert confirmed_context is not None
    assert "status=confirmed_selection" in confirmed_context
    assert "get_stock_by_branches sku=CEM-50" in confirmed_context
    assert "create_quote_draft" in confirmed_context
    assert "cantidad=50" in confirmed_context


def test_customer_can_confirm_candidate_by_natural_option_without_internal_codes() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    first = container.hermes_tools.prepare_customer_turn(
        "necesito 50 bultos para fundir una placa",
        conversation_id="natural-selection",
    )
    confirmed = container.hermes_tools.prepare_customer_turn(
        "La primera opción",
        conversation_id="natural-selection",
    )

    assert first is not None
    assert "1. Cemento gris 50 kg" in first.customer_reply
    assert "CEM-50" not in first.customer_reply
    assert confirmed is not None
    assert "Preparé un borrador" in confirmed.customer_reply
    assert "50 bultos" in confirmed.customer_reply
    assert "CEM-50" not in confirmed.customer_reply
    assert "SKU" not in confirmed.customer_reply


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
