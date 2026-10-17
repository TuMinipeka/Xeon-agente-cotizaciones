import asyncio
import json

import httpx

from xeon.adapters.channels.evolution import (
    EvolutionAPIChannelAdapter,
    parse_evolution_webhook,
)
from xeon.api.app import create_app
from xeon.config import Settings


def _sample_upsert_payload(
    *,
    text: str = "necesito 50 bultos de cemento",
    from_me: bool = False,
    remote_jid: str = "573001112233@s.whatsapp.net",
) -> dict[str, object]:
    return {
        "event": "messages.upsert",
        "instance": "xeon-ferreteria",
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": from_me,
                "id": "BAE5F9A123",
            },
            "message": {
                "conversation": text,
            },
        },
    }


def test_parse_evolution_webhook_normalizes_customer_message_and_ignores_echoes() -> None:
    parsed = parse_evolution_webhook(_sample_upsert_payload())
    assert parsed is not None
    assert parsed.instance == "xeon-ferreteria"
    assert parsed.external_message_id == "BAE5F9A123"
    assert parsed.sender_number == "573001112233"
    assert parsed.text == "necesito 50 bultos de cemento"

    assert parse_evolution_webhook(_sample_upsert_payload(from_me=True)) is None
    assert parse_evolution_webhook(_sample_upsert_payload(remote_jid="12036304@g.us")) is None


def test_parse_evolution_webhook_preserves_friend_lid_and_ignores_owner_sender() -> None:
    payload = _sample_upsert_payload(
        text="/xeon quiero comprar cemento",
        from_me=False,
        remote_jid="28089706877067@lid",
    )
    payload["sender"] = "573247571239@s.whatsapp.net"

    parsed = parse_evolution_webhook(payload, require_prefix=True)
    assert parsed is not None
    assert parsed.sender_jid == "28089706877067@lid"
    assert parsed.sender_number == "28089706877067@lid"
    assert parsed.text == "quiero comprar cemento"


def test_evolution_adapter_sends_text_using_expected_contract() -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == "http://evolution-api:8080/message/sendText/xeon-ferreteria"
            assert request.headers["apikey"] == "evo-secret"
            body = json.loads(request.content)
            assert body == {"number": "573001112233", "text": "Cotizacion lista"}
            return httpx.Response(201, json={"key": {"id": "OUT-999"}})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = EvolutionAPIChannelAdapter(
            base_url="http://evolution-api:8080/",
            instance="xeon-ferreteria",
            api_key="evo-secret",
            client=client,
        )
        receipt = await adapter.send_text(
            recipient_number="573001112233",
            text="Cotizacion lista",
        )
        await client.aclose()

        assert receipt.status == "ACCEPTED_BY_PROVIDER"
        assert receipt.provider_message_id == "OUT-999"

    asyncio.run(run())


def test_whatsapp_webhook_processes_message_with_hermes_and_dispatches_reply() -> None:
    sent_messages: list[tuple[str, str]] = []

    async def run() -> tuple[httpx.Response, httpx.Response]:
        def evo_handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            sent_messages.append((body["number"], body["text"]))
            return httpx.Response(201, json={"key": {"id": "OUT-101"}})

        evo_client = httpx.AsyncClient(transport=httpx.MockTransport(evo_handler))
        whatsapp_adapter = EvolutionAPIChannelAdapter(
            base_url="http://evolution-api:8080",
            instance="xeon-ferreteria",
            api_key="evo-secret",
            client=evo_client,
        )
        settings = Settings(llm_provider="mock", _env_file=None)
        app = create_app(settings=settings, whatsapp_channel=whatsapp_adapter)
        transport = httpx.ASGITransport(app=app)
        event_payload = _sample_upsert_payload(text="cemento")
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/v1/channels/whatsapp/webhook",
                json=event_payload,
            )
            duplicate = await client.post(
                "/v1/channels/whatsapp/webhook",
                json=event_payload,
            )
        await evo_client.aclose()
        return first, duplicate

    response, duplicate_response = asyncio.run(run())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["sender_number"] == "573001112233"
    assert payload["delivery_status"] == "ACCEPTED_BY_PROVIDER"
    assert "CEM-50" in payload["reply"]
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["status"] == "ignored"
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "573001112233"
    assert "28900.00" in sent_messages[0][1]
