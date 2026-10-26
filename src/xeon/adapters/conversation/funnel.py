import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from xeon.application.ports.funnel import FunnelState


class InMemoryFunnelRepository:
    def __init__(self) -> None:
        self._states: dict[str, FunnelState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def conversation(self, key: str) -> AsyncIterator[None]:
        async with self._locks.setdefault(key, asyncio.Lock()):
            yield

    def get(self, conversation_key: str) -> FunnelState:
        return self._states.get(conversation_key, FunnelState())

    def save(self, conversation_key: str, state: FunnelState) -> None:
        self._states[conversation_key] = state
