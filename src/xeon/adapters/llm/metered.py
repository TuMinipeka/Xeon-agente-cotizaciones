from __future__ import annotations

import time
from collections.abc import Sequence

from xeon.application.observability import TokenPricing, current_step, current_task
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse
from xeon.application.ports.metrics import MetricEvent, MetricsRecorder


class MeteredLLM:
    """Records latency, reported tokens and configured-rate cost for every completion."""

    def __init__(
        self, inner: LLMPort, recorder: MetricsRecorder, pricing: TokenPricing | None = None
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._pricing = pricing

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model(self) -> str:
        return self._inner.model

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        started = time.perf_counter()
        try:
            response = await self._inner.complete(messages)
        except BaseException:
            self._emit(started, None, ok=False)
            raise
        self._emit(started, response, ok=True)
        return response

    def _emit(self, started: float, response: LLMResponse | None, *, ok: bool) -> None:
        usage = response.usage if response is not None else None
        known = usage is not None and usage.known
        self._recorder.record(
            MetricEvent(
                stage="llm",
                duration_ms=(time.perf_counter() - started) * 1000,
                ts=time.time(),
                task=current_task(),
                step=current_step(),
                ok=ok,
                provider=self.provider_name,
                model=self.model,
                prompt_tokens=usage.prompt_tokens if known and usage else None,
                completion_tokens=usage.completion_tokens if known and usage else None,
                usage_known=known,
                estimated_cost=self._pricing.cost(usage) if self._pricing else None,
                cost_unit=self._pricing.unit if self._pricing and known else None,
            )
        )

    async def aclose(self) -> None:
        await self._inner.aclose()
