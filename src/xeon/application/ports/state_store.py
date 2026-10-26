"""Transaction boundary and processed inbound message contract."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class StateTransaction(Protocol):
    def conversation(self, key: str) -> AbstractAsyncContextManager[None]: ...

    def close(self) -> None: ...


class ProcessedEventStore(Protocol):
    def claim(self, instance: str, message_id: str) -> bool: ...
