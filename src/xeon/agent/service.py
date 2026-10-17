from __future__ import annotations

from xeon.agent.hermes import HermesToolbelt
from xeon.agent.prompts import SYSTEM_PROMPT
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


class AgentService:
    def __init__(self, llm: LLMPort, tools: HermesToolbelt | None = None) -> None:
        self._llm = llm
        self._tools = tools

    @property
    def tools(self) -> HermesToolbelt | None:
        return self._tools

    async def respond(self, user_message: str) -> LLMResponse:
        message_list: list[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
        ]
        if self._tools is not None:
            verified_context = self._tools.format_verified_context(user_message)
            if verified_context is not None:
                message_list.append(ChatMessage(role="system", content=verified_context))
        message_list.append(ChatMessage(role="user", content=user_message))
        return await self._llm.complete(tuple(message_list))

    async def aclose(self) -> None:
        await self._llm.aclose()
