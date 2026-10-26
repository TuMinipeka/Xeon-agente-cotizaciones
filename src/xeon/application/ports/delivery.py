"""Durable inbound and outbound delivery contracts, independent of SQL and HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from xeon.application.ports.channels import IncomingWhatsAppMessage
from xeon.application.reply import Reply


@dataclass(frozen=True, slots=True)
class ClaimedInbound:
    message: IncomingWhatsAppMessage
    token: str
    attempts: int


@dataclass(frozen=True, slots=True)
class ClaimedOutbound:
    key: str
    recipient_number: str
    reply: Reply
    token: str
    attempts: int


class InboundQueue(Protocol):
    def put(self, message: IncomingWhatsAppMessage) -> bool: ...

    def claim_due(self) -> ClaimedInbound | None: ...

    def complete(self, claimed: ClaimedInbound) -> None: ...

    def retry(self, claimed: ClaimedInbound) -> None: ...


class OutboundQueue(Protocol):
    def put(
        self,
        *,
        key: str,
        recipient_number: str,
        reply: Reply,
        advisor_event_id: UUID | None = None,
    ) -> bool: ...

    def claim_due(self) -> ClaimedOutbound | None: ...

    def sent(self, claimed: ClaimedOutbound, provider_message_id: str | None) -> None: ...

    def failed(
        self, claimed: ClaimedOutbound, *, permanent: bool, status_code: int | None
    ) -> None: ...
