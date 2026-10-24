from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from pydantic import SecretStr

from xeon.adapters.channels.kapso import KapsoChannelAdapter
from xeon.agent.service import AgentService
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.ports.channels import ChannelDeliveryError
from xeon.config import Settings

SECRET = "test-webhook-secret"


def _event(message_id: str, *, kind: str = "text") -> dict[str, object]:
    return {
        "phone_number_id": "phone-123",
        "conversation": {"phone_number": "+573001112233"},
        "message": {"id": message_id, "type": kind, "text": {"body": "necesito cemento"}},
    }


def _headers(raw: bytes, *, event: str = "whatsapp.message.received") -> dict[str, str]:
    return {
        "X-Webhook-Signature": hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest(),
        "X-Webhook-Event": event,
        "Content-Type": "application/json",
    }


def _settings() -> Settings:
    return Settings(
        llm_provider="mock",
        kapso_webhook_secret=SecretStr(SECRET),
        kapso_webhook_secret_file=None,
        _env_file=None,
    )


def test_signed_webhook_dispatches_once_with_kapso_payload_and_dedup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[httpx.Request] = []
    calls: list[tuple[str | None, str | None]] = []
    original_respond = AgentService.respond

    async def tracked_respond(
        self: AgentService,
        message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
    ) -> object:
        calls.append((conversation_key, request_id))
        return await original_respond(
            self, message, conversation_key=conversation_key, request_id=request_id
        )

    monkeypatch.setattr(AgentService, "respond", tracked_respond)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"messages": [{"id": "out-1"}]})

    async def run() -> None:
        kapso_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = KapsoChannelAdapter(
            base_url="https://api.kapso.test",
            phone_number_id="phone-123",
            graph_version="v24.0",
            api_key="test-api-key",
            client=kapso_client,
        )
        app = create_app(settings=_settings(), whatsapp_channel=adapter)
        raw = json.dumps(_event("in-1")).encode()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post(
                "/v1/channels/whatsapp/kapso/webhook", content=raw, headers=_headers(raw)
            )
            second = await client.post(
                "/v1/channels/whatsapp/kapso/webhook", content=raw, headers=_headers(raw)
            )
        await kapso_client.aclose()
        assert first.status_code == 200 and first.json() == {"status": "processed"}
        assert second.status_code == 200 and second.json() == {"status": "ignored"}

    asyncio.run(run())
    assert len(sent) == 1
    assert calls == [("kapso-phone-123-573001112233", "kapso-in-1")]
    assert str(sent[0].url) == "https://api.kapso.test/meta/whatsapp/v24.0/phone-123/messages"
    assert sent[0].headers["X-API-Key"] == "test-api-key"
    payload = json.loads(sent[0].content)
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "573001112233"
    assert payload["type"] == "text"
    assert "cemento" in payload["text"]["body"].lower()


def test_missing_or_invalid_signature_returns_401_without_processing() -> None:
    async def run() -> None:
        app = create_app(settings=_settings())
        raw = json.dumps(_event("in-2")).encode()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            missing = await client.post("/v1/channels/whatsapp/kapso/webhook", content=raw)
            invalid = await client.post(
                "/v1/channels/whatsapp/kapso/webhook",
                content=raw,
                headers={**_headers(raw), "X-Webhook-Signature": "0" * 64},
            )
        assert missing.status_code == invalid.status_code == 401

    asyncio.run(run())


def test_other_event_and_non_text_are_ignored() -> None:
    async def run() -> None:
        app = create_app(settings=_settings())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            raw = json.dumps(_event("in-3")).encode()
            other = await client.post(
                "/v1/channels/whatsapp/kapso/webhook",
                content=raw,
                headers=_headers(raw, event="whatsapp.message.sent"),
            )
            raw_image = json.dumps(_event("in-4", kind="image")).encode()
            image = await client.post(
                "/v1/channels/whatsapp/kapso/webhook",
                content=raw_image,
                headers=_headers(raw_image),
            )
        assert other.json() == image.json() == {"status": "ignored"}

    asyncio.run(run())


def test_signed_batch_processes_each_text_message_once() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"messages": [{"id": "out"}]})

    async def run() -> None:
        kapso_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = KapsoChannelAdapter(
            base_url="https://api.kapso.test",
            phone_number_id="phone-123",
            graph_version="v24.0",
            api_key="test-api-key",
            client=kapso_client,
        )
        app = create_app(settings=_settings(), whatsapp_channel=adapter)
        raw = json.dumps([_event("in-5"), _event("in-6"), _event("in-5")]).encode()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/channels/whatsapp/kapso/webhook",
                content=raw,
                headers={**_headers(raw), "X-Webhook-Batch": "true"},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "processed"}
        await kapso_client.aclose()

    asyncio.run(run())
    assert len(sent) == 2


def test_container_selects_kapso_when_sending_is_enabled() -> None:
    async def run() -> None:
        kapso = build_container(
            Settings(
                llm_provider="mock",
                whatsapp_send_enabled=True,
                kapso_api_key=SecretStr("test-api-key"),
                kapso_phone_number_id="phone-123",
                _env_file=None,
            )
        )
        assert isinstance(kapso.whatsapp_channel, KapsoChannelAdapter)
        await kapso.aclose()

    asyncio.run(run())


def test_kapso_http_error_is_sanitized() -> None:
    async def run() -> None:
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(403, text="private upstream details")
            )
        )
        adapter = KapsoChannelAdapter(
            base_url="https://api.kapso.test",
            phone_number_id="phone-123",
            graph_version="v24.0",
            api_key="test-api-key",
            client=client,
        )
        with pytest.raises(ChannelDeliveryError, match="HTTP 403") as error:
            await adapter.send_text(recipient_number="+573001112233", text="hola")
        assert "private upstream details" not in str(error.value)
        assert "test-api-key" not in str(error.value)
        await client.aclose()

    asyncio.run(run())
