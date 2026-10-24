"""E1-E10 remain strict expected failures until their product fixes land."""

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


@pytest.mark.xfail(strict=True, reason="E1: punto de miles interpretado como decimal")
def test_e1_thousand_separator() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("cotice 1.000 bultos de cemento")
            assert any(
                Decimal(line["quantity"]) == 1000
                for draft in sut.drafts()
                for line in draft["lines"]
            )
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E2: sede sur perdida al separar la clausula")
def test_e2_branch_in_same_sentence() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("10 bultos de cemento y entrega en sede sur")
            assert any("sede_solicitada=sede-sur" in context for context in sut.llm.tool_contexts())
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E3: surtido activa sede sur por subcadena")
def test_e3_surtido_does_not_select_south() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("Cotice 20 bultos de cemento surtido en sede norte")
            assert sut.llm.tool_contexts()
            assert all(
                "sede_solicitada=sede-sur" not in context for context in sut.llm.tool_contexts()
            )
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E4: idempotencia devuelve borrador previo con otras lineas")
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


@pytest.mark.xfail(strict=True, reason="E5: fecha fija del chat marca stock vencido como fresh")
def test_e5_current_stock_freshness() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("hay 10 bultos de cemento en sede norte?")
            assert any("vigencia=stale" in context for context in sut.llm.tool_contexts())
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E6: fallo de stock oculto por except Exception pass")
def test_e6_stock_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    async def check() -> None:
        sut = _sut()

        def fail(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("stock unavailable")

        monkeypatch.setattr(sut.container.get_stock_by_branches, "execute", fail)
        try:
            await sut.respond("hay 10 bultos de cemento en sede norte?")
            assert any("stock_unavailable" in context for context in sut.llm.tool_contexts())
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
@pytest.mark.xfail(strict=True, reason="E7: saludo o contexto con coma activa aviso de alcance")
def test_e7_commercial_request_with_comma_has_no_scope_notice(message: str) -> None:
    async def check() -> None:
        sut = _sut()
        try:
            response = await sut.respond(message)
            assert "Sobre la parte que no corresponde a la ferreter" not in response["reply"]
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E8: recogida en sede norte bloqueada por alcance")
def test_e8_pickup_followup_remains_commercial() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("cotice 10 bultos de cemento")
            response = await sut.respond("Lo recojo en la sede norte.")
            assert response["provider"] != "local-policy"
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E9: pedido de dos productos no crea borrador multilinea")
def test_e9_multiple_products_create_multiline_draft() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("cotice 10 bultos de cemento y 5 tubos PVC de 1/2 pulgada")
            assert any(len(draft["lines"]) >= 2 for draft in sut.drafts())
        finally:
            await sut.aclose()

    asyncio.run(check())


@pytest.mark.xfail(strict=True, reason="E10: candidatos semanticos ambiguos crean borrador")
def test_e10_ambiguous_product_requires_clarification_before_draft() -> None:
    async def check() -> None:
        sut = _sut()
        try:
            await sut.respond("cotice 10 tubos pvc")
            assert any(context.count("- SKU=") > 1 for context in sut.llm.tool_contexts())
            assert not sut.drafts()
        finally:
            await sut.aclose()

    asyncio.run(check())
