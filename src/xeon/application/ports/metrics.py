"""Operational metrics port: latency, tokens and estimated cost per turn stage.

Events never carry personal data: no phone number, message text or conversation key.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MetricEvent:
    stage: str
    duration_ms: float
    ts: float
    task: str = "chat"
    step: str | None = None
    operation: str | None = None
    ok: bool = True
    provider: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    # False means the provider did not report usage; tokens are then unknown, never estimated.
    usage_known: bool = False
    estimated_cost: Decimal | None = None
    cost_unit: str | None = None


class MetricsRecorder(Protocol):
    def record(self, event: MetricEvent) -> None: ...
