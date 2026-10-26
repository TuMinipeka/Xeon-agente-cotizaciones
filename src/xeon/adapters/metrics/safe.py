"""Metrics are best effort and cannot abort commercial state transactions."""

from __future__ import annotations

import logging

from xeon.application.ports.metrics import MetricEvent, MetricsRecorder

_LOG = logging.getLogger("xeon.metrics")


class BestEffortMetrics:
    def __init__(self, inner: MetricsRecorder) -> None:
        self._inner = inner

    def record(self, event: MetricEvent) -> None:
        try:
            self._inner.record(event)
        except Exception as exc:
            _LOG.warning("Metrics sink unavailable: %s", type(exc).__name__)
