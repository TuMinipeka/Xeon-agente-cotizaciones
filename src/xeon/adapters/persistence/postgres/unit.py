"""One database transaction and advisory lock per conversation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from sqlalchemy import Connection, Engine, create_engine, text


class PostgresUnit:
    def __init__(self, url: str, *, tenant_id: str) -> None:
        self._engine: Engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        self._tenant_id = tenant_id
        self._current: ContextVar[Connection | None] = ContextVar(
            "xeon_state_connection", default=None
        )

    def key(self, conversation_key: str) -> str:
        return f"{self._tenant_id}:{conversation_key}"

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        current = self._current.get()
        if current is not None:
            yield current
        else:
            with self._engine.begin() as connection:
                yield connection

    @asynccontextmanager
    async def conversation(self, key: str) -> AsyncIterator[None]:
        if self._current.get() is not None:
            yield
            return
        with self._engine.begin() as connection:
            await asyncio.to_thread(
                connection.execute,
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": self.key(key)},
            )
            token = self._current.set(connection)
            try:
                yield
            finally:
                self._current.reset(token)

    def close(self) -> None:
        self._engine.dispose()
