from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from xeon.agent.prompts import SYSTEM_PROMPT
from xeon.application.commercial_turn import (
    DEFAULT_CHAT_BRANCH_ID,
    DEFAULT_CHAT_TENANT_ID,
    SYNTHETIC_CHAT_EVALUATED_AT,
    CommercialTurn,
)
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    text: str
    provider: str
    model: str
    tools_used: tuple[str, ...] = ()
    outcome: str = "conversation"
    quote_id: UUID | None = None


class AgentService:
    def __init__(
        self,
        llm: LLMPort,
        commercial_turn: CommercialTurn,
        *,
        provider: str,
        model: str,
    ) -> None:
        self._llm = llm
        self._commercial_turn = commercial_turn
        self._provider = provider
        self._model = model

    async def respond(
        self,
        user_message: str,
        *,
        conversation_id: UUID,
        tenant_id: str = DEFAULT_CHAT_TENANT_ID,
        requested_branch_id: str = DEFAULT_CHAT_BRANCH_ID,
        evaluated_at: str = SYNTHETIC_CHAT_EVALUATED_AT,
    ) -> AgentTurnResult:
        commercial = self._commercial_turn.execute(
            user_message,
            tenant_id=tenant_id,
            request_id=str(conversation_id),
            requested_branch_id=requested_branch_id,
            evaluated_at=evaluated_at,
        )
        if commercial.outcome != "no_commercial_request":
            return AgentTurnResult(
                text=commercial.reply,
                provider=self._provider,
                model=self._model,
                tools_used=commercial.tools_used,
                outcome=commercial.outcome,
                quote_id=None if commercial.quote is None else commercial.quote.id,
            )

        llm = await self._complete(user_message)
        return AgentTurnResult(
            text=llm.text,
            provider=llm.provider,
            model=llm.model,
            tools_used=(),
            outcome="conversation",
        )

    async def _complete(self, user_message: str) -> LLMResponse:
        messages = (
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        )
        return await self._llm.complete(messages)

    async def aclose(self) -> None:
        await self._llm.aclose()
