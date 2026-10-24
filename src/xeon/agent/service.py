from __future__ import annotations

from xeon.agent.hermes import HermesToolbelt
from xeon.agent.prompts import SYSTEM_PROMPT
from xeon.application.ports.conversation_memory import ConversationMemory
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


class AgentService:
    def __init__(
        self,
        llm: LLMPort,
        tools: HermesToolbelt | None = None,
        memory: ConversationMemory | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._memory = memory

    @property
    def tools(self) -> HermesToolbelt | None:
        return self._tools

    async def respond(
        self,
        user_message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
    ) -> LLMResponse:
        message_list: list[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
        ]
        previous_sku = (
            self._memory.last_sku(conversation_key)
            if self._memory is not None and conversation_key is not None
            else None
        )
        selected_sku: str | None = None
        if self._tools is not None:
            verified_context, selected_sku = self._tools.prepare_verified_context(
                user_message, request_id=request_id, last_sku=previous_sku
            )
            if verified_context is not None:
                message_list.append(ChatMessage(role="system", content=verified_context))
        if self._memory is not None and conversation_key is not None:
            message_list.extend(self._memory.history(conversation_key))
        message_list.append(ChatMessage(role="user", content=user_message))
        response = await self._llm.complete(tuple(message_list))
        if self._memory is not None and conversation_key is not None:
            self._memory.record(conversation_key, user_message, response.text, selected_sku)
        return response

    async def aclose(self) -> None:
        await self._llm.aclose()
