from __future__ import annotations

from xeon.agent.prompts import SYSTEM_PROMPT
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


class AgentService:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def respond(self, user_message: str) -> LLMResponse:
        messages = (
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        )
        return await self._llm.complete(messages)

    async def aclose(self) -> None:
        await self._llm.aclose()
