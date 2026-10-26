"""Run the durable Kapso delivery worker without starting the HTTP API."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from xeon.application.container import build_container
from xeon.application.delivery_worker import DeliveryWorker
from xeon.config import get_settings


async def main() -> None:
    runtime = build_container(get_settings())
    try:
        if (
            runtime.inbound_queue is None
            or runtime.outbound_queue is None
            or runtime.state_unit is None
            or runtime.processed_events is None
        ):
            raise SystemExit("El proceso de entregas requiere STATE_STORE=postgres.")
        worker = DeliveryWorker(
            inbound=runtime.inbound_queue,
            outbound=runtime.outbound_queue,
            state=runtime.state_unit,
            processed=runtime.processed_events,
            agent=runtime.agent,
            channel=runtime.whatsapp_channel,
            poll_seconds=runtime.settings.delivery_poll_seconds,
        )
        await worker.run_forever(asyncio.Event())
    finally:
        await runtime.aclose()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
