"""Quote PDF: document data, ReportLab rendering and the authenticated download route."""

from __future__ import annotations

import asyncio
import io
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.test_advisor_panel import KEY, PHONE, FakeChannel, _confirm, _login, _settings
from xeon.api.app import create_app
from xeon.application.container import AppContainer, build_container
from xeon.application.policy_schema import StorePolicy
from xeon.application.ports.quote_pdf import QuotePdfDocument
from xeon.application.quote_document import LEGEND, build_quote_pdf_document, format_cop
from xeon.domain.quote import Quote, QuoteStatus

TODAY = date(2026, 10, 26)


def _confirmed(container: AppContainer) -> Quote:
    assert container.advisor_inbox is not None
    event = next(e for e in container.advisor_inbox.list_events() if e.kind == "client_confirmed")
    quote = container.quotes.get(event.quote_id)  # type: ignore[arg-type]
    assert quote is not None
    return quote


def _document(container: AppContainer) -> QuotePdfDocument:
    quote = _confirmed(container)
    return build_quote_pdf_document(
        quote,
        state=container.agent.conversation_state(KEY),
        policy=container.policies.load(quote.tenant_id),
        tenant_id=quote.tenant_id,
        branch_name="Sede Norte",
        issued_on=TODAY,
    )


@pytest.fixture
def container(tmp_path: Path) -> AppContainer:
    built = build_container(_settings(tmp_path), whatsapp_channel=FakeChannel())
    asyncio.run(_confirm(built))
    return built


def test_cop_format_uses_dots_and_no_decimals() -> None:
    from decimal import Decimal

    assert format_cop(Decimal("289000")) == "$289.000"
    assert format_cop(Decimal("1234500.00")) == "$1.234.500"


def test_document_carries_quote_policy_and_conversation_data_without_the_phone(
    container: AppContainer,
) -> None:
    document = _document(container)
    assert (
        document.legend
        == LEGEND
        == ("Borrador de cotización - no es factura ni reserva de inventario")
    )
    assert document.total == "$289.000" and document.currency == "COP"
    assert document.number.startswith("COT-") and document.version == 1
    assert document.store_name == "Ferretería demo XEON (datos ficticios)"
    assert document.delivery == "Recoger en sede" and document.branch == "Sede Norte"
    assert document.validity == "3 días desde la emisión"
    assert "pendiente de confirmar con un asesor" in document.tax_note
    assert document.lines[0].subtotal == "$289.000"
    assert PHONE not in repr(document) and KEY not in repr(document)


def test_missing_policy_values_are_shown_as_pending(container: AppContainer) -> None:
    quote = _confirmed(container)
    document = build_quote_pdf_document(
        quote,
        state=container.agent.conversation_state("sin-estado"),
        policy=StorePolicy(),
        tenant_id="acme",
        branch_name=None,
        issued_on=TODAY,
    )
    assert document.store_name == "acme"
    assert (
        document.payment
        == document.validity
        == document.delivery
        == ("pendiente de confirmar con un asesor")
    )


def test_renderer_writes_a_pdf_with_accents_amounts_and_legend(container: AppContainer) -> None:
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from xeon.adapters.pdf.reportlab_renderer import ReportlabQuotePdfRenderer

    document = _document(container)
    content = ReportlabQuotePdfRenderer().render(document)
    assert content.startswith(b"%PDF-")
    assert content == ReportlabQuotePdfRenderer().render(document)  # deterministic bytes
    reader = pypdf.PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    flat = " ".join(text.split())
    for expected in (
        LEGEND,
        document.number,
        "versión 1",
        "Cotización",
        "$289.000",
        "COP",
        "Recoger en sede",
        "Sede Norte",
        "Vigencia: 3 días desde la emisión",
        "IVA: pendiente de confirmar con un asesor",
        "Forma de pago",
        "Ferretería demo XEON (datos ficticios)",
        "emitida el 2026-10-26",
    ):
        assert expected in flat, expected
    assert flat.count(LEGEND) == 2
    assert PHONE not in flat


# ---------- route ----------


class _FakeRenderer:
    def render(self, document: QuotePdfDocument) -> bytes:
        return b"%PDF-fake " + document.number.encode()


def _client(container: AppContainer, monkeypatch: pytest.MonkeyPatch, *, real: bool = False):  # type: ignore[no-untyped-def]
    if not real:
        monkeypatch.setattr("xeon.api.panel.load_pdf_renderer", lambda: _FakeRenderer())
    return TestClient(create_app(container=container), follow_redirects=False)


def test_pdf_route_requires_a_session(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(container, monkeypatch) as client:
        assert client.get(f"/panel/quotes/{_confirmed(container).id}/pdf").status_code == 401


def test_pdf_route_downloads_attachment_for_confirmed_and_reviewed_quotes(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    quote = _confirmed(container)
    with _client(container, monkeypatch) as client:
        _login(client)
        response = client.get(f"/panel/quotes/{quote.id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment;") and "cotizacion-COT-" in disposition
        assert response.content.startswith(b"%PDF-")
        assert "Descargar PDF" in client.get("/panel/events/" + str(_event_id(container))).text


def _event_id(container: AppContainer):  # type: ignore[no-untyped-def]
    assert container.advisor_inbox is not None
    return next(e.id for e in container.advisor_inbox.list_events() if e.kind == "client_confirmed")


def test_pdf_route_returns_404_for_unknown_or_invalid_ids(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(container, monkeypatch) as client:
        _login(client)
        assert client.get(f"/panel/quotes/{uuid4()}/pdf").status_code == 404
        assert client.get("/panel/quotes/no-es-uuid/pdf").status_code == 404


def test_pdf_route_refuses_an_unconfirmed_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = build_container(_settings(tmp_path), whatsapp_channel=FakeChannel())

    async def to_summary() -> None:
        for message in (
            "start:products",
            "cemento gris 50kg",
            "product:CEM-50",
            "quantity:10",
            "more:view",
            "delivery:pickup",
            "branch:sede-norte",
            "payment:0",
        ):
            await container.agent.respond_reply(message, conversation_key=KEY)

    asyncio.run(to_summary())
    draft = next(q for q in container.quotes._quotes.values())  # type: ignore[attr-defined]
    assert draft.status is QuoteStatus.DRAFT
    assert container.advisor_inbox is not None
    container.advisor_inbox.notify(
        tenant_id=draft.tenant_id, event="client_confirmed", conversation_key=KEY, quote_id=draft.id
    )
    with _client(container, monkeypatch) as client:
        _login(client)
        assert client.get(f"/panel/quotes/{draft.id}/pdf").status_code == 409


def test_pdf_route_reports_503_when_the_pdf_group_is_missing(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("xeon.api.panel.load_pdf_renderer", lambda: None)
    with TestClient(create_app(container=container), follow_redirects=False) as client:
        _login(client)
        assert client.get(f"/panel/quotes/{_confirmed(container).id}/pdf").status_code == 503


def test_pdf_route_with_the_real_renderer(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    with _client(container, monkeypatch, real=True) as client:
        _login(client)
        response = client.get(f"/panel/quotes/{_confirmed(container).id}/pdf")
    assert response.status_code == 200
    reader = pypdf.PdfReader(io.BytesIO(response.content))
    assert LEGEND in " ".join(reader.pages[0].extract_text().split())
