"""Regression tests for A1: nobody can plant the draft a customer later confirms."""

from __future__ import annotations

import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient

from xeon.agent.executor import CommercialExecutor
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.quote_draft import CreateQuoteDraftCommand, DraftLineRequest
from xeon.config import Settings
from xeon.domain.quote import QuoteStatus

KEY = "kapso-999000111-573001234567"


def _container():  # type: ignore[no-untyped-def]
    return build_container(
        Settings(llm_provider="mock", xeon_api_auth_disabled=True, _env_file=None)
    )


def test_api_rejects_foreign_tenants_and_reserved_request_ids() -> None:
    container = _container()
    client = TestClient(create_app(container=container))
    body = {"request_id": "pedido-1", "lines": [{"query": "CEM-50", "quantity": 1}]}
    foreign = client.post("/v1/quotes", json={**body, "tenant_id": "otro-tenant"})
    assert foreign.status_code == 400 and "tenant" in foreign.json()["detail"]
    for reserved in ("xeon-abc", "XEON-abc", "kapso-wamid.1"):
        response = client.post(
            "/v1/quotes", json={**body, "request_id": reserved, "tenant_id": "whatsapp"}
        )
        assert response.status_code == 400, reserved
    assert (
        client.get(
            "/v1/quotes/00000000-0000-4000-8000-000000000000", params={"tenant_id": "otro-tenant"}
        ).status_code
        == 400
    )
    ok = client.post("/v1/quotes", json={**body, "tenant_id": "whatsapp"})
    assert ok.status_code == 201


def test_confirmation_fails_closed_when_the_stored_draft_differs_from_the_cart() -> None:
    """Sonda P4: a draft planted under the customer's idempotency key must not be confirmed."""
    container = _container()
    planted_id = CommercialExecutor._quote_request_id(KEY, 1)
    planted = container.create_quote_draft.execute(
        CreateQuoteDraftCommand(
            tenant_id="whatsapp",
            request_id=planted_id,
            lines=(DraftLineRequest(query="CEM-50", quantity=Decimal(1)),),
        )
    )
    assert planted.__class__.__name__ == "QuoteDraftReady"

    async def customer() -> str:
        text = ""
        for message in (
            "start:products",
            "cemento gris 50kg",
            "product:CEM-50",
            "quantity:10",
            "more:view",
            "delivery:pickup",
            "branch:sede-norte",
            "payment:0",
            "summary:confirm",
        ):
            text = (await container.agent.respond_reply(message, conversation_key=KEY)).text
        return text

    final = asyncio.run(customer())
    assert "pendiente de confirmar con un asesor" in final
    assert all(q.status is QuoteStatus.DRAFT for q in container.quotes._quotes.values())  # type: ignore[attr-defined]
    assert container.advisor_inbox is not None
    assert [e for e in container.advisor_inbox.list_events() if e.kind == "client_confirmed"] == []
    assert container.agent.conversation_state(KEY).step != "confirmado"


def test_confirmation_still_works_when_draft_and_cart_match() -> None:
    container = _container()

    async def customer() -> None:
        for message in (
            "start:products",
            "cemento gris 50kg",
            "product:CEM-50",
            "quantity:10",
            "more:view",
            "delivery:pickup",
            "branch:sede-norte",
            "payment:0",
            "summary:confirm",
        ):
            await container.agent.respond_reply(message, conversation_key="web-1")

    asyncio.run(customer())
    confirmed = [
        q
        for q in container.quotes._quotes.values()  # type: ignore[attr-defined]
        if q.status is QuoteStatus.CONFIRMADO_POR_CLIENTE
    ]
    assert len(confirmed) == 1 and confirmed[0].lines[0].quantity == Decimal(10)
