import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from xeon.application.ports.funnel import FunnelState


class InMemoryFunnelRepository:
    def __init__(self, *, max_conversations: int = 10_000) -> None:
        self._states: OrderedDict[str, FunnelState] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._max = max_conversations

    @asynccontextmanager
    async def conversation(self, key: str) -> AsyncIterator[None]:
        async with self._locks.setdefault(key, asyncio.Lock()):
            yield

    def get(self, conversation_key: str) -> FunnelState:
        state = self._states.get(conversation_key)
        if state is None:
            return FunnelState()
        self._states.move_to_end(conversation_key)
        return state

    def save(self, conversation_key: str, state: FunnelState) -> None:
        self._states[conversation_key] = state
        self._states.move_to_end(conversation_key)
        while len(self._states) > self._max:
            evicted, _ = self._states.popitem(last=False)
            self._locks.pop(evicted, None)
