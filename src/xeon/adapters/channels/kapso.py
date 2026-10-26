from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from xeon.adapters.channels.whatsapp_formatter import WhatsAppFormatter
from xeon.application.ports.channels import (
    ChannelDeliveryError,
    IncomingWhatsAppMessage,
    WhatsAppSendReceipt,
)
from xeon.application.reply import Reply


def verify_kapso_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or len(signature) != 64:
        return False
    try:
        supplied = bytes.fromhex(signature)
    except ValueError:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(expected, supplied)


def parse_kapso_webhook(
    payload: Any, *, idempotency_key: str | None = None
) -> IncomingWhatsAppMessage | None:
    """Read a single signed v2 message event after the endpoint checks its event header."""
    if not isinstance(payload, dict):
        return None
    message = payload.get("message")
    conversation = payload.get("conversation")
    if not isinstance(message, dict) or not isinstance(conversation, dict):
        return None
    option_id = None
    if message.get("type") == "interactive":
        interactive = message.get("interactive")
        if not isinstance(interactive, dict):
            return None
        choice = interactive.get("button_reply") or interactive.get("list_reply")
        if not isinstance(choice, dict) or not isinstance(choice.get("id"), str):
            return None
        option_id = choice["id"].strip()
        text = str(choice.get("title") or option_id).strip()
    elif message.get("type") == "text":
        text_obj = message.get("text")
        if not isinstance(text_obj, dict) or not isinstance(text_obj.get("body"), str):
            return None
        text = text_obj["body"].strip()
    else:
        return None
    phone_id = payload.get("phone_number_id")
    phone = conversation.get("phone_number")
    message_id = message.get("id") or idempotency_key
    if not all(isinstance(value, str) and value.strip() for value in (phone_id, phone, message_id)):
        return None
    if not text:
        return None
    assert isinstance(phone_id, str) and isinstance(phone, str) and isinstance(message_id, str)
    number = phone.strip().lstrip("+")
    if not number.isdigit():
        return None
    return IncomingWhatsAppMessage(
        instance=phone_id.strip(),
        external_message_id=message_id.strip(),
        sender_jid=phone.strip(),
        sender_number=number,
        text=text,
        raw_payload=payload,
        option_id=option_id,
    )


class KapsoChannelAdapter:
    """Send text and interactive replies through Kapso's Meta proxy."""

    def __init__(
        self,
        *,
        base_url: str,
        phone_number_id: str,
        graph_version: str,
        api_key: str,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not phone_number_id.strip():
            raise ValueError("KAPSO_PHONE_NUMBER_ID es obligatorio para enviar mensajes.")
        self._phone_number_id = phone_number_id.strip()
        self._url = (
            f"{base_url.rstrip('/')}/meta/whatsapp/{graph_version.strip()}/"
            f"{self._phone_number_id}/messages"
        )
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._formatter = WhatsAppFormatter()

    async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt:
        return await self.send_reply(recipient_number=recipient_number, reply=Reply(text))

    async def send_reply(self, *, recipient_number: str, reply: Reply) -> WhatsAppSendReceipt:
        number = recipient_number.strip().lstrip("+")
        if not number.isdigit():
            raise ChannelDeliveryError("Numero de destino invalido para Kapso.")
        body: dict[str, Any] = {"messaging_product": "whatsapp", "to": number}
        if reply.kind == "text":
            body.update({"type": "text", "text": {"body": self._formatter.format(reply.text)}})
        elif reply.kind == "buttons":
            body.update(
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": self._formatter.format(reply.text)},
                        "action": {
                            "buttons": [
                                {"type": "reply", "reply": {"id": item.id, "title": item.title}}
                                for item in reply.options
                            ]
                        },
                    },
                }
            )
        else:
            body.update(
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "list",
                        "body": {"text": self._formatter.format(reply.text)},
                        "action": {
                            "button": "Ver opciones",
                            "sections": [
                                {
                                    "title": "Opciones",
                                    "rows": [
                                        {"id": item.id, "title": item.title}
                                        for item in reply.options
                                    ],
                                }
                            ],
                        },
                    },
                }
            )
        try:
            response = await self._client.post(
                self._url,
                headers={"X-API-Key": self._api_key},
                json=body,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ChannelDeliveryError(
                f"Kapso respondio con HTTP {exc.response.status_code}.",
                status_code=exc.response.status_code,
            ) from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ChannelDeliveryError(
                "No fue posible entregar el mensaje a traves de Kapso."
            ) from exc

        provider_id: str | None = None
        if isinstance(body, dict):
            messages = body.get("messages")
            if isinstance(messages, list) and messages and isinstance(messages[0], dict):
                identifier = messages[0].get("id")
                if isinstance(identifier, str):
                    provider_id = identifier
        return WhatsAppSendReceipt(
            instance=self._phone_number_id,
            recipient_number=number,
            provider_message_id=provider_id,
            status="ACCEPTED_BY_PROVIDER",
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
