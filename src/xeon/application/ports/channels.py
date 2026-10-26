from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from xeon.application.reply import Reply


class ChannelDeliveryError(RuntimeError):
    """Sanitized channel delivery failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class IncomingWhatsAppMessage:
    instance: str
    external_message_id: str
    sender_jid: str
    sender_number: str
    text: str
    raw_payload: dict[str, Any]
    option_id: str | None = None


@dataclass(frozen=True, slots=True)
class WhatsAppSendReceipt:
    instance: str
    recipient_number: str
    provider_message_id: str | None
    status: str


class WhatsAppChannelPort(Protocol):
    async def send_text(self, *, recipient_number: str, text: str) -> WhatsAppSendReceipt: ...

    async def send_reply(self, *, recipient_number: str, reply: Reply) -> WhatsAppSendReceipt: ...

    async def aclose(self) -> None: ...
