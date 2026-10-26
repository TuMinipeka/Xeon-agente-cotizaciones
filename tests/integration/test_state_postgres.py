"""Operational state across container instances using the XEON-owned PostgreSQL."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from xeon.adapters.persistence.postgres.repositories import ConcurrentCartUpdate
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.ports.channels import WhatsAppSendReceipt
from xeon.application.reply import Reply
from xeon.config import Settings
from xeon.domain.cart import QuoteCart

pytestmark = pytest.mark.integration
SECRET = "state-test-webhook-secret"


@pytest.fixture
def settings() -> Settings:
    path = Path("secrets/xeon_state_url.txt")
    if not path.is_file():
        pytest.skip("Create the local XEON state URL file as documented in docs/PERSISTENCIA.md")
    value = Settings(
        llm_provider="mock",
        state_store="postgres",
        xeon_state_url_file=path,
        kapso_webhook_secret=SecretStr(SECRET),
        kapso_webhook_secret_file=None,
        _env_file=None,
    )
    engine = create_engine(value.require_state_url(), hide_parameters=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE processed_events, quote_drafts, conversation_memories, "
                    "cart_states, funnel_states"
                )
            )
    finally:
        engine.dispose()
    return value


def test_restart_preserves_funnel_cart_quote_and_project_context(settings: Settings) -> None:
    async def run() -> None:
        first = build_container(settings)
        key = "state-restart"
        try:
            for message in ("start:products", "cemento", "product:CEM-50", "quantity:10"):
                await first.agent.respond_reply(message, conversation_key=key)
            cart = first.carts.get(key)
            assert cart is not None and cart.confirmed_lines()[0].quantity == 10
            await first.agent.respond_reply(
                "toda la superficie 20x30 dame lista materiales corral ganado "
                "no preguntes mas medidas",
                conversation_key=key,
            )
            assert first.conversation_memory.project_data(key).area_m2 == 600
        finally:
            await first.aclose()
        second = build_container(settings)
        try:
            assert second.agent._funnel.state(key).step == "proyecto"
            assert second.conversation_memory.project_data(key).area_m2 == 600
            saved = second.carts.get(key)
            assert saved is not None and saved.confirmed_lines()[0].quantity == 10
            assert second.agent._funnel._cart(key).find("289.000") >= 0
            assert (
                second.quotes.get_by_idempotency_key(
                    settings.tenant_id, second.agent._funnel._executor.current_quote_request_id(key)
                )
                is not None
            )
        finally:
            await second.aclose()

    asyncio.run(run())


def test_two_workers_claim_one_webhook_and_make_one_draft(settings: Settings) -> None:
    sent: list[Reply] = []

    class Channel:
        async def send_reply(self, *, recipient_number: str, reply: Reply) -> WhatsAppSendReceipt:
            sent.append(reply)
            return WhatsAppSendReceipt("phone-123", recipient_number, "out", "ACCEPTED_BY_PROVIDER")

        async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt:
            return await self.send_reply(recipient_number=recipient_number, reply=Reply(text))

        async def aclose(self) -> None:
            pass

    async def run() -> None:
        channel = Channel()
        first = build_container(settings, whatsapp_channel=channel)
        second = build_container(settings, whatsapp_channel=channel)
        key = "kapso-phone-123-573001112233"
        try:
            for message in ("start:products", "cemento", "product:CEM-50"):
                await first.agent.respond_reply(message, conversation_key=key)
            event = {
                "phone_number_id": "phone-123",
                "conversation": {"phone_number": "+573001112233"},
                "message": {
                    "id": "same-message-id",
                    "type": "interactive",
                    "interactive": {"button_reply": {"id": "quantity:10", "title": "10"}},
                },
            }
            raw = json.dumps(event).encode()
            headers = {
                "X-Webhook-Signature": hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest(),
                "X-Webhook-Event": "whatsapp.message.received",
                "Content-Type": "application/json",
            }
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=create_app(container=first)),
                    base_url="http://worker-one",
                ) as client_one,
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=create_app(container=second)),
                    base_url="http://worker-two",
                ) as client_two,
            ):
                responses = await asyncio.gather(
                    *(
                        client.post(
                            "/v1/channels/whatsapp/kapso/webhook", content=raw, headers=headers
                        )
                        for client in (client_one, client_two)
                    )
                )
            assert all(response.status_code == 200 for response in responses)
            assert len(sent) == 1
            cart = first.carts.get(key)
            assert cart is not None and cart.confirmed_lines()[0].quantity == 10
            engine = create_engine(settings.require_state_url(), hide_parameters=True)
            try:
                with engine.connect() as connection:
                    assert (
                        connection.execute(text("SELECT count(*) FROM quote_drafts")).scalar() == 1
                    )
                    assert (
                        connection.execute(text("SELECT count(*) FROM processed_events")).scalar()
                        == 1
                    )
            finally:
                engine.dispose()
        finally:
            await first.aclose()
            await second.aclose()

    asyncio.run(run())


def test_concurrent_cart_writers_reject_stale_version(settings: Settings) -> None:
    first = build_container(settings)
    second = build_container(settings)
    try:
        product = first.catalog.find_exact("CEM-50")
        assert product is not None
        first.carts.save(QuoteCart("cart-race").add_item(product, 1))
        barrier = Barrier(2)

        def update(container: object, amount: int) -> str:
            repository = container.carts  # type: ignore[attr-defined]
            cart = repository.get("cart-race")
            assert cart is not None
            changed = cart.set_quantity("CEM-50", amount)
            barrier.wait(timeout=5)
            try:
                repository.save(changed)
            except ConcurrentCartUpdate:
                return "stale"
            return "saved"

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(update, first, 2)
            b = pool.submit(update, second, 3)
            assert sorted((a.result(), b.result())) == ["saved", "stale"]
        saved = first.carts.get("cart-race")
        assert saved is not None and saved.version == 2
        assert saved.confirmed_lines()[0].quantity in {2, 3}
    finally:
        asyncio.run(first.aclose())
        asyncio.run(second.aclose())


def test_tenants_do_not_share_conversation_state(settings: Settings) -> None:
    alpha = build_container(settings.model_copy(update={"tenant_id": "alpha"}))
    beta = build_container(settings.model_copy(update={"tenant_id": "beta"}))

    async def run() -> None:
        try:
            await alpha.agent.respond_reply("start:products", conversation_key="same-key")
            assert alpha.agent._funnel.state("same-key").step == "producto"
            assert beta.agent._funnel.state("same-key").step == "inicio"
        finally:
            await alpha.aclose()
            await beta.aclose()

    asyncio.run(run())
