"""Outbound retry classification using Kapso HTTP doubles, without paid calls."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx

from xeon.adapters.channels.kapso import KapsoChannelAdapter
from xeon.application.delivery_worker import DeliveryWorker
from xeon.application.ports.delivery import ClaimedOutbound
from xeon.application.reply import Reply


class EmptyInbound:
    def claim_due(self):  # type: ignore[no-untyped-def]
        return None


class FakeOutbound:
    def __init__(self) -> None:
        self.pending: ClaimedOutbound | None = None
        self.sent_count = 0
        self.failed_count = 0
        self.permanent = False
        self.keys: set[str] = set()

    def put(self, key: str) -> bool:
        if key in self.keys:
            return False
        self.keys.add(key)
        self.pending = ClaimedOutbound(key, "573001112233", Reply("hola"), str(uuid4()), 0)
        return True

    def claim_due(self) -> ClaimedOutbound | None:
        item, self.pending = self.pending, None
        if item is None:
            return None
        return ClaimedOutbound(
            item.key, item.recipient_number, item.reply, item.token, item.attempts + 1
        )

    def sent(self, claimed: ClaimedOutbound, provider_message_id: str | None) -> None:
        assert provider_message_id == "wamid.test"
        self.sent_count += 1

    def failed(self, claimed: ClaimedOutbound, *, permanent: bool, status_code: int | None) -> None:
        self.failed_count += 1
        self.permanent = permanent
        if not permanent:
            self.pending = claimed


def _run(statuses: list[int]) -> tuple[FakeOutbound, list[int]]:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "test-only"
        code = statuses[len(seen)]
        seen.append(code)
        return httpx.Response(code, json={"messages": [{"id": "wamid.test"}]})

    async def exercise() -> FakeOutbound:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        channel = KapsoChannelAdapter(
            base_url="https://api.kapso.ai",
            phone_number_id="phone-test",
            graph_version="v24.0",
            api_key="test-only",
            client=client,
        )
        queue = FakeOutbound()
        assert queue.put("one")
        assert not queue.put("one")
        worker = DeliveryWorker(
            inbound=EmptyInbound(),  # type: ignore[arg-type]
            outbound=queue,  # type: ignore[arg-type]
            state=None,  # type: ignore[arg-type]
            processed=None,  # type: ignore[arg-type]
            agent=None,  # type: ignore[arg-type]
            channel=channel,
        )
        try:
            for _ in statuses:
                await worker.run_once()
            return queue
        finally:
            await client.aclose()

    return asyncio.run(exercise()), seen


def test_transient_http_failure_retries_once_and_duplicate_key_never_resends() -> None:
    queue, calls = _run([503, 200])
    assert calls == [503, 200]
    assert queue.failed_count == 1 and queue.sent_count == 1
    assert not queue.permanent


def test_client_error_is_final_without_infinite_retry() -> None:
    queue, calls = _run([400, 200])
    assert calls == [400]
    assert queue.failed_count == 1 and queue.sent_count == 0
    assert queue.permanent and queue.pending is None


def test_kapso_conversation_conflict_is_retryable() -> None:
    queue, calls = _run([409, 200])
    assert calls == [409, 200]
    assert queue.sent_count == 1
