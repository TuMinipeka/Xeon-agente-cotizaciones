from __future__ import annotations

from xeon.agent.customer_safety import CustomerResponsePolicy
from xeon.agent.hermes import HermesToolbelt
from xeon.agent.prompts import SYSTEM_PROMPT
from xeon.application.commercial_scope import CommercialScopePolicy
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


class AgentService:
    def __init__(
        self,
        llm: LLMPort,
        tools: HermesToolbelt | None = None,
        *,
        scope_policy: CommercialScopePolicy | None = None,
        response_policy: CustomerResponsePolicy | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._scope_policy = scope_policy or CommercialScopePolicy()
        self._response_policy = response_policy or CustomerResponsePolicy()

    @property
    def tools(self) -> HermesToolbelt | None:
        return self._tools

    async def respond(
        self,
        user_message: str,
        *,
        conversation_id: str | None = None,
    ) -> LLMResponse:
        scope = self._scope_policy.classify(user_message)
        if scope.blocks_llm:
            return LLMResponse(
                text=scope.customer_message or "¿Necesitas ayuda con algún producto de ferretería?",
                provider="local-policy",
                model="commercial-scope-v1",
            )

        commercial_message = scope.commercial_query or user_message
        message_list: list[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
        ]
        customer_fallback = (
            "No encuentro suficiente información para ayudarte con ese producto. "
            "¿Puedes contarme qué necesitas y en qué cantidad?"
        )
        if self._tools is not None:
            prepared = self._tools.prepare_customer_turn(
                commercial_message,
                conversation_id=conversation_id,
            )
            if prepared is not None:
                customer_fallback = prepared.customer_reply
                if prepared.verified_context is not None:
                    message_list.append(
                        ChatMessage(role="system", content=prepared.verified_context)
                    )
                message_list.append(
                    ChatMessage(
                        role="system",
                        content=f"[XEON_CUSTOMER_DRAFT]\n{prepared.customer_reply}",
                    )
                )
        message_list.append(ChatMessage(role="user", content=commercial_message))
        result = await self._llm.complete(tuple(message_list))
        safe_reply = self._response_policy.sanitize(result.text, fallback=customer_fallback)
        if scope.kind == "mixed" and scope.customer_message is not None:
            safe_reply = f"{scope.customer_message}\n\n{safe_reply}"
        return LLMResponse(text=safe_reply, provider=result.provider, model=result.model)

    async def aclose(self) -> None:
        await self._llm.aclose()
