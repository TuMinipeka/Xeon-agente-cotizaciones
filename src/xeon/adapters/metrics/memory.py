from __future__ import annotations

from xeon.application.ports.metrics import MetricEvent


class NullMetrics:
    def record(self, event: MetricEvent) -> None:
        return None


class InMemoryMetrics:
    """Keeps events in the process; used by tests and the evaluation runner."""

    def __init__(self, *, max_events: int = 10_000) -> None:
        self.events: list[MetricEvent] = []
        self._max_events = max_events

    def record(self, event: MetricEvent) -> None:
        if len(self.events) >= self._max_events:
            del self.events[: self._max_events // 10]
        self.events.append(event)
