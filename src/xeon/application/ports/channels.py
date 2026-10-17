from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ChannelDeliveryError(RuntimeError):
    """Sanitized channel delivery failure."""


@dataclass(frozen=True, slots=True)
class IncomingWhatsAppMessage:
    instance: str
    external_message_id: str
    sender_jid: str
    sender_number: str
    text: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WhatsAppSendReceipt:
    instance: str
    recipient_number: str
    provider_message_id: str | None
    status: str


class WhatsAppChannelPort(Protocol):
    async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt: ...

    async def aclose(self) -> None: ...

