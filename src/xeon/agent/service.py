"""Single guided commercial conversation boundary."""

from __future__ import annotations

from xeon.agent.guided_funnel import GuidedFunnel
from xeon.application.ports.llm import LLMPort, LLMResponse
from xeon.application.reply import Reply


class AgentService:
    def __init__(self, llm: LLMPort, *, funnel: GuidedFunnel) -> None:
        self._llm = llm
        self._funnel = funnel

    async def respond_reply(
        self,
        user_message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
        option_id: str | None = None,
    ) -> Reply:
        return await self._funnel.handle(
            conversation_key or "anonymous",
            user_message,
            option_id=option_id,
            request_id=request_id,
        )

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
