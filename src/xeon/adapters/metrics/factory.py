from __future__ import annotations

from xeon.adapters.metrics.jsonl import JsonlMetrics
from xeon.adapters.metrics.memory import NullMetrics
from xeon.application.observability import TokenPricing
from xeon.application.ports.metrics import MetricsRecorder
from xeon.config import Settings


def build_metrics(settings: Settings) -> MetricsRecorder:
    if settings.metrics_path is None:
        return NullMetrics()
    return JsonlMetrics(settings.metrics_path)


def build_pricing(settings: Settings) -> TokenPricing | None:
    """Rates are an assumption the operator configures; without both there is no cost."""
    if settings.llm_price_input_per_mtok is None or settings.llm_price_output_per_mtok is None:
        return None
    return TokenPricing(
        settings.llm_price_input_per_mtok,
        settings.llm_price_output_per_mtok,
        settings.llm_price_unit,
    )
