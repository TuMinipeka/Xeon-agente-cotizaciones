from __future__ import annotations

import re
from typing import Any

import httpx

from xeon.application.ports.channels import (
    ChannelDeliveryError,
    IncomingWhatsAppMessage,
    WhatsAppSendReceipt,
)


def _normalize_number(remote_jid: str) -> str:
    user_part = remote_jid.split("@", 1)[0]
    digits = re.sub(r"\D+", "", user_part)
    return digits or user_part.strip()


def _extract_message_text(message_obj: dict[str, Any]) -> str:
    conversation = message_obj.get("conversation")
    if isinstance(conversation, str) and conversation.strip():
        return conversation.strip()

    extended = message_obj.get("extendedTextMessage")
    if isinstance(extended, dict):
        text = extended.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

    return ""


def parse_evolution_webhook(payload: dict[str, Any]) -> IncomingWhatsAppMessage | None:
    """Normalize an Evolution API webhook event into an IncomingWhatsAppMessage.

    Ignores non-message events, outbound echoes (fromMe=True), status broadcasts,
    and group messages.
    """
    event = str(payload.get("event", "")).strip().lower()
    if event not in {"messages.upsert", "messages_upsert"}:
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    key = data.get("key")
    if not isinstance(key, dict):
        return None

    if bool(key.get("fromMe", False)):
        return None

    remote_jid = str(key.get("remoteJid", "")).strip()
    if not remote_jid or remote_jid.endswith("@g.us") or remote_jid == "status@broadcast":
        return None

    message_obj = data.get("message")
    if not isinstance(message_obj, dict):
        return None

    text = _extract_message_text(message_obj)
    if not text:
        return None

    instance = str(payload.get("instance", "default")).strip() or "default"
    external_id = str(key.get("id", "")).strip()
    if not external_id:
        return None

    return IncomingWhatsAppMessage(
        instance=instance,
        external_message_id=external_id,
        sender_jid=remote_jid,
        sender_number=_normalize_number(remote_jid),
        text=text,
        raw_payload=payload,
    )


class EvolutionAPIChannelAdapter:
    """WhatsApp channel adapter using a self-hosted Evolution API instance."""

    def __init__(
        self,
        *,
        base_url: str,
        instance: str,
        api_key: str,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._instance = instance.strip()
        self._url = f"{base_url.rstrip('/')}/message/sendText/{self._instance}"
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt:
        payload = {
            "number": recipient_number.strip(),
            "text": text,
        }
        try:
            response = await self._client.post(
                self._url,
                headers={
                    "apikey": self._api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ChannelDeliveryError(
                f"Evolution API respondio con HTTP {exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ChannelDeliveryError(
                "No fue posible entregar el mensaje a traves de Evolution API."
            ) from exc

        provider_id: str | None = None
        if isinstance(body, dict):
            key = body.get("key")
            if isinstance(key, dict) and isinstance(key.get("id"), str):
                provider_id = key["id"]

        return WhatsAppSendReceipt(
            instance=self._instance,
            recipient_number=recipient_number.strip(),
            provider_message_id=provider_id,
            status="ACCEPTED_BY_PROVIDER",
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
