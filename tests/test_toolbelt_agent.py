import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from tests.guided_steps import add_product
from xeon.adapters.branches.memory import InMemoryBranchDirectory
from xeon.agent.tool_trace import capture_tool_events
from xeon.agent.toolbelt import _extract_requested_quantity
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.ports.branches import resolve_branch
from xeon.application.quote_draft import DraftLineRequest, QuoteDraftReady
from xeon.config import Settings


def test_colombian_quantities_and_branch_word_boundaries() -> None:
    assert _extract_requested_quantity("quiero 1.000 bultos") == Decimal(1000)
    assert _extract_requested_quantity("quiero 1.500 bultos") == Decimal(1500)
    assert _extract_requested_quantity("quiero 2,5 metros") == Decimal("2.5")
    assert _extract_requested_quantity("quiero 2.5 metros") == Decimal("2.5")
    branches = InMemoryBranchDirectory()
    assert resolve_branch("surtido en sede norte", branches).id == "sede-norte"
    assert resolve_branch("entrega en sede sur", branches).id == "sede-sur"


def test_injected_clock_controls_stock_freshness() -> None:
    settings = Settings(llm_provider="mock", _env_file=None)
    fresh = build_container(settings, clock=lambda: datetime(2026, 10, 8, 15, 0, tzinfo=UTC))
    stale = build_container(settings, clock=lambda: datetime(2026, 10, 24, 15, 0, tzinfo=UTC))

    async def option(container, key):  # type: ignore[no-untyped-def]
        await add_product(container, key, "cemento", "CEM-50", 10)
        await container.agent.respond_reply("more:view", conversation_key=key)
        return await container.agent.respond_reply("delivery:pickup", conversation_key=key)

    fresh_reply = asyncio.run(option(fresh, "fresh"))
    stale_reply = asyncio.run(option(stale, "stale"))
    fresh_title = next(item.title for item in fresh_reply.options if item.id == "branch:sede-norte")
    stale_title = next(item.title for item in stale_reply.options if item.id == "branch:sede-norte")
    assert "disponible" in fresh_title
    assert "pendiente" in stale_title


def test_quote_failure_is_visible_without_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private detail")

    monkeypatch.setattr(container.create_quote_draft, "execute", fail)
    reply = asyncio.run(add_product(container, "error", "cemento", "CEM-50", 10))
    assert "No pude actualizar el borrador" in reply.text
    assert "private detail" not in reply.text


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


def test_tool_trace_records_three_real_invocations_without_customer_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))
    with capture_tool_events() as events:

        async def journey() -> None:
            key = "kapso-phone-123-+573001112233"
            await add_product(container, key, "cemento", "CEM-50", 2)
            await container.agent.respond_reply("more:view", conversation_key=key)
            await container.agent.respond_reply("delivery:pickup", conversation_key=key)
            await container.agent.respond_reply("branch:sede-norte", conversation_key=key)

        asyncio.run(journey())

    assert any(event == "TOOL search_products status=exact_match sku=CEM-50" for event in events)
    assert any(
        event.startswith("TOOL get_stock_by_branches sku=CEM-50 sede=sede-norte")
        for event in events
    )
    assert any("lineas=1 subtotal=57800.00 COP" in event for event in events)
    emitted = [record.message for record in caplog.records if record.name == "xeon.tools"]
    assert emitted == events
    assert "+573001112233" not in "\n".join(emitted)


def test_speculative_product_lookup_has_one_effective_trace_line() -> None:
    container = build_container(Settings(llm_provider="mock", _env_file=None))
    with capture_tool_events() as events:

        async def search() -> None:
            await container.agent.respond_reply("start:products", conversation_key="trace-once")
            await container.agent.respond_reply("tubos pvc", conversation_key="trace-once")

        asyncio.run(search())

    search_events = [event for event in events if event.startswith("TOOL search_products")]
    assert len(search_events) == 1
    assert "sku=TUB-PVC-20" in search_events[0]


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
            await client.post(
                "/v1/chat",
                json={
                    "message": "start:products",
                    "conversation_id": "00000000-0000-0000-0000-000000000999",
                },
            )
            return await client.post(
                "/v1/chat",
                json={
                    "message": "busco material para fundir placa y pegar ladrillo",
                    "conversation_id": "00000000-0000-0000-0000-000000000999",
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "CEM-50" in reply
    assert "28900.00" not in reply  # An unchosen candidate has no quoted price.
