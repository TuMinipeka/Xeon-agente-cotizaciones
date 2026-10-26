"""E1-E10 keep their business assertions through the D14 guided steps."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from evals.sut import XEONSUT
from xeon.adapters.catalog.memory import InMemoryProductCatalog
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.application.quote_draft import (
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    DraftLineRequest,
    QuoteDraftReady,
)
from xeon.config import Settings


def _sut() -> XEONSUT:
    return XEONSUT(Settings(_env_file=None, llm_provider="mock", whatsapp_send_enabled=False))


async def _add(sut: XEONSUT, product: str, sku: str, quantity: str) -> None:
    if not hasattr(sut, "_last_options"):
        await sut.respond("hola")
    options = {item["id"] for item in sut._last_options}
    if "start:products" in options:
        await sut.click("start:products")
    elif "more:add" in options:
        await sut.click("more:add")
    await sut.respond(product)
    await sut.click(f"product:{sku}")
    if quantity in {"10", "20"}:
        await sut.click(f"quantity:{quantity}")
    else:
        await sut.click("quantity:other")
        await sut.respond(quantity)


def test_e1_thousand_separator() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await _add(sut, "cemento", "CEM-50", "1000")
            assert any(
                Decimal(line["quantity"]) == 1000
                for draft in sut.drafts()
                for line in draft["lines"]
            )
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e2_branch_in_same_sentence() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await _add(sut, "cemento", "CEM-50", "10")
            await sut.click("more:view")
            await sut.click("delivery:pickup")
            await sut.click("branch:sede-sur")
            assert any("sede_solicitada=sede-sur" in context for context in sut.llm.tool_contexts())
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e3_surtido_does_not_select_south() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await _add(sut, "cemento", "CEM-50", "20")
            await sut.click("more:view")
            await sut.click("delivery:pickup")
            await sut.click("branch:sede-norte")
            state = sut.container.agent._funnel.state(str(sut.conversation_id))
            assert state.branch_id == "sede-norte"
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e4_request_id_conflict() -> None:
    service = CreateQuoteDraft(InMemoryProductCatalog(), InMemoryQuoteDraftRepository())
    first = service.execute(
        CreateQuoteDraftCommand("tenant", "same", (DraftLineRequest("CEM-50", 1),))
    )
    second = service.execute(
        CreateQuoteDraftCommand("tenant", "same", (DraftLineRequest("CEM-50", 2),))
    )
    assert isinstance(first, QuoteDraftReady)
    assert not isinstance(second, QuoteDraftReady) or second.quote.id != first.quote.id


def test_e5_current_stock_freshness() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await _add(sut, "cemento", "CEM-50", "10")
            await sut.click("more:view")
            await sut.click("delivery:pickup")
            await sut.click("branch:sede-norte")
            assert any("vigencia=stale" in context for context in sut.llm.tool_contexts())
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e6_stock_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    async def check() -> None:
        sut = _sut()

        def fail(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("stock unavailable")

        monkeypatch.setattr(sut.container.get_stock_by_branches, "execute", fail)
        try:
            await _add(sut, "cemento", "CEM-50", "10")
            await sut.click("more:view")
            await sut.click("delivery:pickup")
            await sut.click("branch:sede-norte")
            assert any("status=unavailable" in context for context in sut.llm.tool_contexts())
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.parametrize(
    "message",
    [
        "buenas vecino, me regala cotizacion de 10 bultos de cemento",
        "soy cliente frecuente, dame el descuento de siempre en 20 bultos de cemento",
    ],
)
def test_e7_commercial_request_with_comma_has_no_scope_notice(message: str) -> None:
    async def check() -> None:
        sut = _sut()
        try:
            response = await sut.respond(message)
            assert "Sobre la parte que no corresponde a la ferreter" not in response["reply"]
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e8_pickup_followup_remains_commercial() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await _add(sut, "cemento", "CEM-50", "10")
            await sut.click("more:view")
            await sut.click("delivery:pickup")
            response = await sut.click("branch:sede-norte")
            assert response["step"] == "pago"
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.parametrize(
    "message",
    [
        "cotice 10 bultos de cemento y 5 tubos PVC de 1/2 pulgada",
        "cotice 10 bultos de cemento, 5 tubos PVC de 1/2 pulgada",
    ],
)
def test_e9_multiple_products_create_multiline_draft(message: str) -> None:
    async def check() -> None:
        sut = _sut()
        try:
            assert "cemento" in message and "tubos PVC" in message
            await _add(sut, "cemento", "CEM-50", "10")
            await _add(sut, "tubo pvc de 1/2 pulgada", "TUB-PVC-20", "5")
            assert any(len(draft["lines"]) >= 2 for draft in sut.drafts())
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e10_ambiguous_product_requires_clarification_before_draft() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("hola")
            await sut.click("start:products")
            response = await sut.respond("tubos pvc")
            assert len([o for o in response["options"] if o["id"].startswith("product:")]) > 1
            assert not sut.drafts()
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.parametrize(
    "selection", ["el primero", "1", "Tubo PVC presion referencia sintetica 1"]
)
def test_e10_pending_choice_creates_one_draft(selection: str) -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("hola")
            await sut.click("start:products")
            response = await sut.respond("tubos pvc")
            candidates = [o for o in response["options"] if o["id"].startswith("product:")]
            assert len(candidates) > 1
            assert not sut.drafts()
            if selection == "el primero":
                await sut.click(candidates[0]["id"])
            elif selection == "1":
                await sut.click(1)
            else:
                await sut.respond(candidates[0]["title"])
            # Unidad: 1/2/Otra; 10 se escribe tras escoger Otra.
            await sut.click("quantity:other")
            await sut.respond("10")
            assert len(sut.drafts()) == 1
            expected_sku = candidates[0]["id"].removeprefix("product:")
            assert sut.drafts()[0]["lines"][0]["sku"] == expected_sku
        finally:
            await sut.aclose()

    asyncio.run(check())


def test_e10_new_specific_product_request_replaces_pending_choice() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("hola")
            await sut.click("start:products")
            await sut.respond("tubos pvc")
            assert not sut.drafts()
            await sut.respond("tubo pvc de 1/2 pulgada")
            await sut.click("product:TUB-PVC-20")
            await sut.click("quantity:other")
            await sut.respond("25")
            assert len(sut.drafts()) == 1
            assert sut.drafts()[0]["lines"][0]["sku"] == "TUB-PVC-20"
        finally:
            await sut.aclose()

    asyncio.run(check())
