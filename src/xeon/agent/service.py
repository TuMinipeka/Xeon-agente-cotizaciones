"""Single guided commercial conversation boundary."""

from __future__ import annotations

import time

from xeon.agent.guided_funnel import GuidedFunnel
from xeon.application.observability import metric_context, record_stage
from xeon.application.ports.llm import LLMPort, LLMResponse
from xeon.application.ports.metrics import MetricsRecorder
from xeon.application.reply import Reply


class AgentService:
    def __init__(
        self, llm: LLMPort, *, funnel: GuidedFunnel, metrics: MetricsRecorder | None = None
    ) -> None:
        self._llm = llm
        self._funnel = funnel
        self._metrics = metrics

    async def respond_reply(
        self,
        user_message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
        option_id: str | None = None,
    ) -> Reply:
        key = conversation_key or "anonymous"
        started = time.perf_counter()
        # The step shown to the metrics is the one the customer was answering; no message text.
        with metric_context(step=self._funnel.state(key).step):
            reply = await self._funnel.handle(
                key, user_message, option_id=option_id, request_id=request_id
            )
            if self._metrics is not None:
                record_stage(self._metrics, "turno", started, operation=reply.step)
        return reply

    async def respond(
        self,
        user_message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
    ) -> LLMResponse:
        reply = await self.respond_reply(
            user_message, conversation_key=conversation_key, request_id=request_id
        )
        return LLMResponse(text=reply.numbered(), provider="local-guided", model="guided-funnel-v1")

    async def aclose(self) -> None:
        await self._llm.aclose()
