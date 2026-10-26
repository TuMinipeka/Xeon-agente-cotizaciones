"""Fresh in-process XEON instance for each evaluation repetition."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx

from evals.recording import RecordingLLM
from xeon.adapters.llm import build_llm
from xeon.adapters.persistence.memory import InMemoryQuoteDraftRepository
from xeon.application.container import AppContainer, build_container
from xeon.config import Settings
from xeon.domain.quote import Quote


class RecordingQuoteRepository(InMemoryQuoteDraftRepository):
    def __init__(self) -> None:
        super().__init__()
        self.saved: list[Quote] = []

    def save(self, quote: Quote) -> Quote:
        saved = super().save(quote)
        self.saved.append(saved)
        return saved


class XEONSUT:
    def __init__(
        self,
        settings: Settings,
        *,
        on_llm_call: Callable[[], None] | None = None,
    ) -> None:
        # Import lazily: xeon.api.app creates a default app on module import.
        from xeon.api.app import create_app

        self.quotes = RecordingQuoteRepository()
        self.llm = RecordingLLM(build_llm(settings), on_call=on_llm_call)
        self.container: AppContainer = build_container(settings, quotes=self.quotes, llm=self.llm)
        self.app = create_app(container=self.container)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://xeon.local"
        )
        self.conversation_id: UUID = uuid4()

    async def respond(self, message: str) -> dict[str, Any]:
        response = await self.client.post(
            "/v1/chat",
            json={"message": message, "conversation_id": str(self.conversation_id)},
        )
        response.raise_for_status()
        payload = dict(response.json())
        self.llm.observe_verified_reply(str(payload.get("reply", "")))
        return payload

    def drafts(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(quote.id),
                "status": quote.status.value,
                "subtotal": str(quote.subtotal.amount),
                "total": str(quote.total.amount),
                "currency": quote.currency,
                "lines": [
                    {
                        "sku": line.sku,
                        "quantity": str(line.quantity),
                        "unit_price": str(line.unit_price.amount),
                        "line_total": str(line.line_total.amount),
                    }
                    for line in quote.lines
                ],
            }
            for quote in self.quotes.saved
        ]

    async def aclose(self) -> None:
        await self.client.aclose()
        await self.container.aclose()
