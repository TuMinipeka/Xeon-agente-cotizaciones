"""Safe, per-turn trace of deterministic commercial tools."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_LOGGER = logging.getLogger("xeon.tools")
_LOGGER.setLevel(logging.INFO)
_LOGGER.propagate = False
if not _LOGGER.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(_handler)

_CURRENT_EVENTS: ContextVar[list[str] | None] = ContextVar("xeon_tool_events", default=None)


@contextmanager
def capture_tool_events() -> Iterator[list[str]]:
    events: list[str] = []
    token = _CURRENT_EVENTS.set(events)
    try:
        yield events
    finally:
        _CURRENT_EVENTS.reset(token)


def record_tool(name: str, **fields: str | int) -> None:
    event = "TOOL " + name + " " + " ".join(f"{key}={value}" for key, value in fields.items())
    _LOGGER.info("%s", event)
    current = _CURRENT_EVENTS.get()
    if current is not None:
        current.append(event)
