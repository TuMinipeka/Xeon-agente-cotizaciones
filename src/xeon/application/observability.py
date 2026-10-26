"""Metric context, timing proxy, cost model and aggregation (no external dependencies)."""

from __future__ import annotations

import inspect
import math
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from functools import wraps
from typing import Any, cast

from xeon.application.ports.llm import TokenUsage
from xeon.application.ports.metrics import MetricEvent, MetricsRecorder

_task: ContextVar[str] = ContextVar("xeon_metric_task", default="chat")
_step: ContextVar[str | None] = ContextVar("xeon_metric_step", default=None)
_MILLION = Decimal(1_000_000)


@contextmanager
def metric_context(*, task: str | None = None, step: str | None = None) -> Iterator[None]:
    """Label every event recorded inside the block with a task (scenario) and funnel step."""
    task_token = _task.set(task) if task is not None else None
    step_token = _step.set(step) if step is not None else None
    try:
        yield
    finally:
        if step_token is not None:
            _step.reset(step_token)
        if task_token is not None:
            _task.reset(task_token)


def current_task() -> str:
    return _task.get()


def current_step() -> str | None:
    return _step.get()


@dataclass(frozen=True, slots=True)
class TokenPricing:
    """Price per million tokens. The unit is configured, never assumed: see docs."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    unit: str

    def cost(self, usage: TokenUsage | None) -> Decimal | None:
        if usage is None or usage.prompt_tokens is None or usage.completion_tokens is None:
            return None
        return (
            Decimal(usage.prompt_tokens) * self.input_per_mtok
            + Decimal(usage.completion_tokens) * self.output_per_mtok
        ) / _MILLION


def record_stage(
    recorder: MetricsRecorder,
    stage: str,
    started: float,
    *,
    operation: str | None = None,
    ok: bool = True,
) -> None:
    recorder.record(
        MetricEvent(
            stage=stage,
            duration_ms=(time.perf_counter() - started) * 1000,
            ts=time.time(),
            task=_task.get(),
            step=_step.get(),
            operation=operation,
            ok=ok,
        )
    )


class _TimedProxy:
    """Wrap an object so each public method call records one stage event."""

    def __init__(
        self, target: object, recorder: MetricsRecorder, stage: str, methods: frozenset[str] | None
    ) -> None:
        self._target = target
        self._recorder = recorder
        self._stage = stage
        self._methods = methods

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._target, name)
        if name.startswith("_") or not callable(attribute):
            return attribute
        if self._methods is not None and name not in self._methods:
            return attribute
        recorder, stage = self._recorder, self._stage
        if inspect.iscoroutinefunction(attribute):

            @wraps(attribute)
            async def timed_async(*args: Any, **kwargs: Any) -> Any:
                started, ok = time.perf_counter(), True
                try:
                    return await attribute(*args, **kwargs)
                except BaseException:
                    ok = False
                    raise
                finally:
                    record_stage(recorder, stage, started, operation=name, ok=ok)

            return timed_async

        @wraps(attribute)
        def timed(*args: Any, **kwargs: Any) -> Any:
            started, ok = time.perf_counter(), True
            try:
                return attribute(*args, **kwargs)
            except BaseException:
                ok = False
                raise
            finally:
                record_stage(recorder, stage, started, operation=name, ok=ok)

        return timed


def timed[T](
    target: T, recorder: MetricsRecorder, stage: str, *, methods: Iterable[str] | None = None
) -> T:
    """Return `target` behind a proxy that times its methods under `stage`.

    Stages are inclusive: a catalog call made inside the executor is counted in both.
    """
    only = frozenset(methods) if methods is not None else None
    return cast(T, _TimedProxy(target, recorder, stage, only))


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile; deterministic and dependency free."""
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def aggregate(events: Iterable[MetricEvent | dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group events by task: calls, tokens, unknown usage, latency p50/p95 per stage and cost."""
    rows = [_as_dict(event) for event in events]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("task", "chat"))].append(row)
    report: dict[str, dict[str, Any]] = {}
    for task, items in sorted(grouped.items()):
        llm = [row for row in items if row["stage"] == "llm"]
        known = [row for row in llm if row.get("usage_known")]
        costs = [Decimal(str(row["estimated_cost"])) for row in known if row.get("estimated_cost")]
        stages: dict[str, dict[str, Any]] = {}
        for stage in sorted({row["stage"] for row in items}):
            durations = [float(row["duration_ms"]) for row in items if row["stage"] == stage]
            stages[stage] = {
                "count": len(durations),
                "p50_ms": round(percentile(durations, 0.50), 3),
                "p95_ms": round(percentile(durations, 0.95), 3),
            }
        units = {str(row["cost_unit"]) for row in known if row.get("cost_unit")}
        report[task] = {
            "llm_calls": len(llm),
            "prompt_tokens": sum(int(row["prompt_tokens"]) for row in known),
            "completion_tokens": sum(int(row["completion_tokens"]) for row in known),
            "usage_unknown_calls": len(llm) - len(known),
            "estimated_cost": str(sum(costs, Decimal(0))) if costs else None,
            "cost_unit": ",".join(sorted(units)) or None,
            "stages": stages,
        }
    return report


def _as_dict(event: MetricEvent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, dict):
        return event
    return {
        "stage": event.stage,
        "task": event.task,
        "duration_ms": event.duration_ms,
        "usage_known": event.usage_known,
        "prompt_tokens": event.prompt_tokens,
        "completion_tokens": event.completion_tokens,
        "estimated_cost": None if event.estimated_cost is None else str(event.estimated_cost),
        "cost_unit": event.cost_unit,
    }
