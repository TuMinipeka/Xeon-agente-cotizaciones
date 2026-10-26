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
from xeon.application.advisor_review import AdvisorReview, ReviewError
from xeon.application.container import build_container
from xeon.application.delivery_worker import DeliveryWorker
from xeon.application.ports.advisor import AdvisorEvent, AttentionStatus
from xeon.application.ports.channels import IncomingWhatsAppMessage, WhatsAppSendReceipt
from xeon.application.ports.metrics import MetricEvent
from xeon.application.reply import Reply
from xeon.config import Settings
from xeon.domain.cart import QuoteCart
from xeon.domain.quote import QuoteStatus, build_draft_quote, build_quote_line

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
                    "TRUNCATE inbound_deliveries, outbound_deliveries, advisor_events, "
                    "processed_events, quote_drafts, "
                    "conversation_memories, cart_states, funnel_states"
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


def test_signed_webhook_is_durable_before_ack_and_outbox_survives_restart(
    settings: Settings,
) -> None:
    disabled = settings.model_copy(update={"delivery_worker_enabled": False})
    event = {
        "phone_number_id": "phone-123",
        "conversation": {"phone_number": "+573001112233"},
        "message": {"id": "durable-001", "type": "text", "text": {"body": "hola"}},
    }
    raw = json.dumps(event).encode()
    headers = {
        "X-Webhook-Signature": hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest(),
        "X-Webhook-Event": "whatsapp.message.received",
        "Content-Type": "application/json",
    }

    class Channel:
        def __init__(self) -> None:
            self.sent: list[Reply] = []

        async def send_reply(self, *, recipient_number: str, reply: Reply) -> WhatsAppSendReceipt:
            assert recipient_number == "573001112233"
            self.sent.append(reply)
            return WhatsAppSendReceipt(
                "phone-123", recipient_number, "wamid.durable", "ACCEPTED_BY_PROVIDER"
            )

        async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt:
            return await self.send_reply(recipient_number=recipient_number, reply=Reply(text))

        async def aclose(self) -> None:
            pass

    async def run() -> None:
        first = build_container(disabled)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_app(container=first)),
                base_url="http://worker-one",
            ) as client:
                response = await client.post(
                    "/v1/channels/whatsapp/kapso/webhook", content=raw, headers=headers
                )
                assert response.status_code == 200
                assert response.json()["status"] == "processed"
            engine = create_engine(settings.require_state_url(), hide_parameters=True)
            try:
                with engine.connect() as connection:
                    assert (
                        connection.execute(
                            text(
                                "SELECT status FROM inbound_deliveries "
                                "WHERE message_id='durable-001'"
                            )
                        ).scalar_one()
                        == "pending"
                    )
                    assert (
                        connection.execute(text("SELECT count(*) FROM processed_events")).scalar()
                        == 0
                    )
            finally:
                engine.dispose()
        finally:
            await first.aclose()

        second = build_container(disabled)
        try:
            assert second.inbound_queue is not None and second.outbound_queue is not None
            assert second.state_unit is not None and second.processed_events is not None
            worker = DeliveryWorker(
                inbound=second.inbound_queue,
                outbound=second.outbound_queue,
                state=second.state_unit,
                processed=second.processed_events,
                agent=second.agent,
                channel=None,
            )
            assert await worker.run_once()
            assert second.agent.conversation_state("kapso-phone-123-573001112233").step == "inicio"
            engine = create_engine(settings.require_state_url(), hide_parameters=True)
            try:
                with engine.connect() as connection:
                    assert (
                        connection.execute(
                            text("SELECT status FROM outbound_deliveries")
                        ).scalar_one()
                        == "pending"
                    )
            finally:
                engine.dispose()
        finally:
            await second.aclose()

        channel = Channel()
        third = build_container(disabled, whatsapp_channel=channel)
        try:
            assert third.inbound_queue is not None and third.outbound_queue is not None
            assert third.state_unit is not None and third.processed_events is not None
            worker = DeliveryWorker(
                inbound=third.inbound_queue,
                outbound=third.outbound_queue,
                state=third.state_unit,
                processed=third.processed_events,
                agent=third.agent,
                channel=channel,
            )
            assert await worker.run_once()
            assert len(channel.sent) == 1
            assert not await worker.run_once()
            engine = create_engine(settings.require_state_url(), hide_parameters=True)
            try:
                with engine.connect() as connection:
                    assert (
                        connection.execute(
                            text("SELECT status FROM inbound_deliveries")
                        ).scalar_one()
                        == "done"
                    )
                    assert (
                        connection.execute(
                            text("SELECT status FROM outbound_deliveries")
                        ).scalar_one()
                        == "sent"
                    )
            finally:
                engine.dispose()
        finally:
            await third.aclose()

    asyncio.run(run())


def test_delivery_queues_keep_conversation_order_and_backoff(settings: Settings) -> None:
    container = build_container(settings)
    try:
        assert container.inbound_queue is not None and container.outbound_queue is not None
        inbound = container.inbound_queue
        outbound = container.outbound_queue
        for message_id in ("ordered-1", "ordered-2"):
            assert inbound.put(
                IncomingWhatsAppMessage(
                    instance="phone-123",
                    external_message_id=message_id,
                    sender_jid="+573001112233",
                    sender_number="573001112233",
                    text="hola",
                    raw_payload={"message": {"id": message_id}},
                )
            )
        first = inbound.claim_due()
        assert first is not None and first.message.external_message_id == "ordered-1"
        assert inbound.claim_due() is None
        inbound.complete(first)
        second = inbound.claim_due()
        assert second is not None and second.message.external_message_id == "ordered-2"
        inbound.complete(second)

        assert outbound.put(key="reply-1", recipient_number="573001112233", reply=Reply("uno"))
        assert outbound.put(key="reply-2", recipient_number="573001112233", reply=Reply("dos"))
        assert not outbound.put(key="reply-1", recipient_number="573001112233", reply=Reply("uno"))
        first_send = outbound.claim_due()
        assert first_send is not None and first_send.key == "reply-1"
        assert outbound.claim_due() is None
        outbound.failed(first_send, permanent=False, status_code=503)
        assert outbound.claim_due() is None
        engine = create_engine(settings.require_state_url(), hide_parameters=True)
        try:
            with engine.connect() as connection:
                row = connection.execute(
                    text(
                        "SELECT status, attempts FROM outbound_deliveries WHERE send_key='reply-1'"
                    )
                ).one()
                assert row == ("pending", 1)
        finally:
            engine.dispose()
    finally:
        asyncio.run(container.aclose())


async def _confirm_for_advisor(container: object, key: str) -> None:
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
        await container.agent.respond_reply(message, conversation_key=key)  # type: ignore[attr-defined]


def test_advisor_inbox_and_review_survive_restart(settings: Settings) -> None:
    async def run() -> None:
        first = build_container(settings)
        try:
            await _confirm_for_advisor(first, "advisor-restart")
            assert first.advisor_inbox is not None
            event = first.advisor_inbox.list_events(status=AttentionStatus.PENDIENTE)[0]
            assert event.quote_id is not None
        finally:
            await first.aclose()
        second = build_container(settings)
        try:
            assert second.advisor_inbox is not None
            saved = second.advisor_inbox.get(event.id)
            assert saved == event
            outcome = AdvisorReview(second.advisor_inbox, second.quotes).approve(
                event.id, advisor="asesor1"
            )
            assert outcome.event.status is AttentionStatus.APROBADO
        finally:
            await second.aclose()
        third = build_container(settings)
        try:
            assert third.advisor_inbox is not None
            assert third.advisor_inbox.get(event.id).status is AttentionStatus.APROBADO  # type: ignore[union-attr]
            quote = third.quotes.get(event.quote_id)
            assert quote is not None and quote.status is QuoteStatus.APPROVED_FOR_BILLING
        finally:
            await third.aclose()

    asyncio.run(run())


def test_advisor_decision_and_client_notice_are_committed_together(settings: Settings) -> None:
    disabled = settings.model_copy(update={"delivery_worker_enabled": False})
    first = build_container(disabled)
    try:
        asyncio.run(_confirm_for_advisor(first, "kapso-phone-123-573001112233"))
        assert first.advisor_inbox is not None and first.outbound_queue is not None
        event = first.advisor_inbox.list_events(status=AttentionStatus.PENDIENTE)[0]

        def enqueue(saved: AdvisorEvent, message: str) -> None:
            first.outbound_queue.put(
                key=f"advisor:{saved.id}:decision",
                recipient_number="573001112233",
                reply=Reply(message),
                advisor_event_id=saved.id,
            )

        AdvisorReview(first.advisor_inbox, first.quotes, on_decision=enqueue).approve(
            event.id, advisor="asesor1"
        )
        engine = create_engine(settings.require_state_url(), hide_parameters=True)
        try:
            with engine.connect() as connection:
                assert (
                    connection.execute(text("SELECT status FROM outbound_deliveries")).scalar_one()
                    == "pending"
                )
        finally:
            engine.dispose()
    finally:
        asyncio.run(first.aclose())

    class Channel:
        async def send_reply(self, *, recipient_number: str, reply: Reply) -> WhatsAppSendReceipt:
            assert recipient_number == "573001112233" and "asesor" in reply.text
            return WhatsAppSendReceipt(
                "phone-123", recipient_number, "wamid.advisor", "ACCEPTED_BY_PROVIDER"
            )

        async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt:
            return await self.send_reply(recipient_number=recipient_number, reply=Reply(text))

        async def aclose(self) -> None:
            pass

    async def dispatch() -> None:
        channel = Channel()
        second = build_container(disabled, whatsapp_channel=channel)
        try:
            assert second.inbound_queue is not None and second.outbound_queue is not None
            assert second.state_unit is not None and second.processed_events is not None
            worker = DeliveryWorker(
                inbound=second.inbound_queue,
                outbound=second.outbound_queue,
                state=second.state_unit,
                processed=second.processed_events,
                agent=second.agent,
                channel=channel,
            )
            assert await worker.run_once()
            assert second.advisor_inbox is not None
            saved = second.advisor_inbox.get(event.id)
            assert saved is not None and saved.client_notified is True
        finally:
            await second.aclose()

    asyncio.run(dispatch())


def test_concurrent_advisor_decisions_only_one_wins(settings: Settings) -> None:
    first = build_container(settings)
    second = build_container(settings)
    try:
        asyncio.run(_confirm_for_advisor(first, "advisor-race"))
        assert first.advisor_inbox is not None and second.advisor_inbox is not None
        event = first.advisor_inbox.list_events(status=AttentionStatus.PENDIENTE)[0]
        assert event.quote_id is not None
        barrier = Barrier(2)

        def decide(container: object, approve: bool) -> str:
            inbox = container.advisor_inbox  # type: ignore[attr-defined]
            quotes = container.quotes  # type: ignore[attr-defined]
            review = AdvisorReview(inbox, quotes)
            barrier.wait(timeout=5)
            try:
                if approve:
                    review.approve(event.id, advisor="asesor1")
                else:
                    review.reject(event.id, advisor="asesor2", reason="Revisar precio")
            except ReviewError:
                return "conflict"
            return "saved"

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(decide, first, True)
            b = pool.submit(decide, second, False)
            assert sorted((a.result(), b.result())) == ["conflict", "saved"]
        saved = first.advisor_inbox.get(event.id)
        quote = first.quotes.get(event.quote_id)
        assert saved is not None and quote is not None
        assert (saved.status, quote.status) in {
            (AttentionStatus.APROBADO, QuoteStatus.APPROVED_FOR_BILLING),
            (AttentionStatus.RECHAZADO, QuoteStatus.RECHAZADO_POR_ASESOR),
        }
    finally:
        asyncio.run(first.aclose())
        asyncio.run(second.aclose())


def test_advisor_inbox_is_isolated_by_tenant(settings: Settings) -> None:
    alpha = build_container(settings.model_copy(update={"tenant_id": "alpha"}))
    beta = build_container(settings.model_copy(update={"tenant_id": "beta"}))
    try:
        assert alpha.advisor_inbox is not None and beta.advisor_inbox is not None
        alpha.advisor_inbox.notify(
            tenant_id="alpha", event="advisor_requested", conversation_key="same-conversation"
        )
        event = alpha.advisor_inbox.list_events()[0]
        assert beta.advisor_inbox.list_events() == ()
        assert beta.advisor_inbox.get(event.id) is None
        product = alpha.catalog.find_exact("CEM-50")
        assert product is not None
        quote = alpha.quotes.save(
            build_draft_quote(
                (build_quote_line(product, 1),), tenant_id="alpha", request_id="tenant-check"
            )
        )
        assert beta.quotes.get(quote.id) is None
        assert beta.quotes.get_by_idempotency_key("alpha", "tenant-check") is None
        with pytest.raises(ReviewError, match="inexistente"):
            AdvisorReview(beta.advisor_inbox, beta.quotes).attend(event.id, advisor="asesor2")
    finally:
        asyncio.run(alpha.aclose())
        asyncio.run(beta.aclose())


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


def test_metrics_failure_does_not_rollback_persisted_turn(settings: Settings) -> None:
    class BrokenMetrics:
        def record(self, event: MetricEvent) -> None:
            raise OSError("unavailable")

    async def run() -> None:
        first = build_container(settings, metrics=BrokenMetrics())
        try:
            key = "metrics-failure"
            for message in ("start:products", "cemento", "product:CEM-50", "quantity:10"):
                await first.agent.respond_reply(message, conversation_key=key)
        finally:
            await first.aclose()
        second = build_container(settings)
        try:
            assert second.agent._funnel.state("metrics-failure").step == "mas"
            cart = second.carts.get("metrics-failure")
            assert cart is not None and cart.confirmed_lines()[0].quantity == 10
            assert second.agent._funnel._cart("metrics-failure").find("289.000") >= 0
        finally:
            await second.aclose()

    asyncio.run(run())
