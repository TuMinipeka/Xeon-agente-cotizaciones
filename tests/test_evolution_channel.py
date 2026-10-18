import asyncio
import json

import httpx

from xeon.adapters.channels.evolution import EvolutionAPIChannelAdapter, parse_evolution_webhook
from xeon.api.app import create_app
from xeon.config import Settings


def _sample_upsert_payload(
    *,
    text: str = "necesito 50 bultos de cemento",
    from_me: bool = False,
    remote_jid: str = "573001112233@s.whatsapp.net",
    external_message_id: str = "BAE5F9A123",
) -> dict[str, object]:
    return {
        "event": "messages.upsert",
        "instance": "xeon-ferreteria",
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": from_me,
                "id": external_message_id,
            },
            "message": {"conversation": text},
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


def test_whatsapp_webhook_processes_and_deduplicates_message() -> None:
    sent_messages: list[tuple[str, str]] = []

    async def run() -> tuple[httpx.Response, httpx.Response]:
        def evo_handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            sent_messages.append((body["number"], body["text"]))
            return httpx.Response(201, json={"key": {"id": "OUT-101"}})

        evo_client = httpx.AsyncClient(transport=httpx.MockTransport(evo_handler))
        adapter = EvolutionAPIChannelAdapter(
            base_url="http://evolution-api:8080",
            instance="xeon-ferreteria",
            api_key="evo-secret",
            client=evo_client,
        )
        app = create_app(
            settings=Settings(llm_provider="mock", _env_file=None),
            whatsapp_channel=adapter,
        )
        transport = httpx.ASGITransport(app=app)
        event = _sample_upsert_payload(text="cemento")
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/v1/channels/whatsapp/webhook", json=event)
            duplicate = await client.post("/v1/channels/whatsapp/webhook", json=event)
        await evo_client.aclose()
        return first, duplicate

    response, duplicate = asyncio.run(run())

    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["sender_number"] == "573001112233"
    assert payload["delivery_status"] == "ACCEPTED_BY_PROVIDER"
    assert "ciudad o zona" in payload["reply"]
    assert duplicate.json()["status"] == "ignored"
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "573001112233"
    assert "SKU" not in sent_messages[0][1]


def test_whatsapp_keeps_location_and_candidate_state_for_same_sender() -> None:
    async def run() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            location = await client.post(
                "/v1/channels/whatsapp/webhook",
                json=_sample_upsert_payload(
                    text="necesito 10 laminas de zinc para una casa",
                    external_message_id="WA-LOCATION-1",
                ),
            )
            candidates = await client.post(
                "/v1/channels/whatsapp/webhook",
                json=_sample_upsert_payload(
                    text="zona norte",
                    external_message_id="WA-CANDIDATE-2",
                ),
            )
            selected = await client.post(
                "/v1/channels/whatsapp/webhook",
                json=_sample_upsert_payload(
                    text="la primera opcion",
                    external_message_id="WA-SELECTED-3",
                ),
            )
        return location, candidates, selected

    location, candidates, selected = asyncio.run(run())

    assert "ciudad o zona" in location.json()["reply"]
    assert "Lamina de zinc calibre 28" in candidates.json()["reply"]
    selected_reply = selected.json()["reply"]
    assert "10 laminas" in selected_reply
    assert "borrador" not in selected_reply.casefold()
    assert "SKU" not in selected_reply
