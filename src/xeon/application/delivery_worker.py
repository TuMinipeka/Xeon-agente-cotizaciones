"""Process durable inbound messages and dispatch transactional outgoing replies."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from xeon.agent.service import AgentService
from xeon.application.ports.channels import ChannelDeliveryError, WhatsAppChannelPort
from xeon.application.ports.delivery import InboundQueue, OutboundQueue
from xeon.application.ports.state_store import ProcessedEventStore, StateTransaction

_LOG = logging.getLogger(__name__)
_RETRYABLE_4XX = {408, 409, 425, 429}


class DeliveryWorker:
    def __init__(
        self,
        *,
        inbound: InboundQueue,
        outbound: OutboundQueue,
        state: StateTransaction,
        processed: ProcessedEventStore,
        agent: AgentService,
        channel: WhatsAppChannelPort | None,
        poll_seconds: float = 0.5,
    ) -> None:
        self.inbound = inbound
        self.outbound = outbound
        self.state = state
        self.processed = processed
        self.agent = agent
        self.channel = channel
        self.poll_seconds = poll_seconds

    async def run_once(self) -> bool:
        did_work = False
        claimed = self.inbound.claim_due()
        if claimed is not None:
            did_work = True
            incoming = claimed.message
            key = f"kapso-{incoming.instance}-{incoming.sender_number}"
            try:
                async with self.state.conversation(key):
                    if self.processed.claim(incoming.instance, incoming.external_message_id):
                        reply = await self.agent.respond_reply(
                            incoming.text,
                            conversation_key=key,
                            request_id=f"kapso-{incoming.external_message_id}",
                            option_id=incoming.option_id,
                        )
                        self.outbound.put(
                            key=f"kapso:{incoming.instance}:{incoming.external_message_id}:reply",
                            recipient_number=incoming.sender_number,
                            reply=reply,
                        )
                    self.inbound.complete(claimed)
            except Exception:
                # The conversation transaction rolled back. Retain the signed input for retry.
                self.inbound.retry(claimed)
                _LOG.warning("Inbound delivery deferred; attempt=%s", claimed.attempts)
        if self.channel is not None:
            outgoing = self.outbound.claim_due()
            if outgoing is not None:
                did_work = True
                try:
                    receipt = await self.channel.send_reply(
                        recipient_number=outgoing.recipient_number, reply=outgoing.reply
                    )
                except ChannelDeliveryError as exc:
                    code = exc.status_code
                    permanent = (
                        code is not None and 400 <= code < 500 and code not in _RETRYABLE_4XX
                    )
                    self.outbound.failed(outgoing, permanent=permanent, status_code=code)
                    _LOG.warning("Outbound delivery deferred; status=%s", code)
                except Exception:
                    self.outbound.failed(outgoing, permanent=False, status_code=None)
                    _LOG.warning("Outbound delivery deferred; transport failure")
                else:
                    self.outbound.sent(outgoing, receipt.provider_message_id)
        return did_work

    async def drain(self, *, limit: int = 20) -> None:
        for _ in range(limit):
            if not await self.run_once():
                return

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                did_work = await self.run_once()
            except Exception as exc:
                _LOG.warning("Delivery worker loop failed: %s", type(exc).__name__)
                did_work = False
            if not did_work:
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self.poll_seconds)
