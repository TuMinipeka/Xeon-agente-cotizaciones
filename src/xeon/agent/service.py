from __future__ import annotations

from xeon.agent.customer_safety import CustomerResponsePolicy
from xeon.agent.prompts import SYSTEM_PROMPT
from xeon.agent.toolbelt import CommercialToolbelt
from xeon.application.commercial_scope import CommercialScopePolicy
from xeon.application.ports.conversation_memory import ConversationMemory
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse

_SAFE_FALLBACK = (
    "No puedo confirmar una respuesta segura con la informacion disponible. "
    "¿Puedes indicar el producto y la cantidad que necesitas?"
)


class AgentService:
    def __init__(
        self,
        llm: LLMPort,
        tools: CommercialToolbelt | None = None,
        memory: ConversationMemory | None = None,
        *,
        scope_policy: CommercialScopePolicy | None = None,
        response_policy: CustomerResponsePolicy | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._memory = memory
        self._scope_policy = scope_policy or CommercialScopePolicy()
        self._response_policy = response_policy or CustomerResponsePolicy()

    @property
    def tools(self) -> CommercialToolbelt | None:
        return self._tools

    async def respond(
        self,
        user_message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
    ) -> LLMResponse:
        scope = self._scope_policy.classify(user_message)
        if scope.kind == "out_of_scope":
            return LLMResponse(
                text=scope.customer_message or _SAFE_FALLBACK,
                provider="local-policy",
                model="commercial-scope-v1",
            )

        commercial_message = scope.commercial_query or user_message
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
                commercial_message, request_id=request_id, last_sku=previous_sku
            )
            if verified_context is not None:
                message_list.append(ChatMessage(role="system", content=verified_context))
        if self._memory is not None and conversation_key is not None:
            message_list.extend(self._memory.history(conversation_key))
        message_list.append(ChatMessage(role="user", content=commercial_message))
        response = await self._llm.complete(tuple(message_list))
        # Mock deliberately exposes tool markers for deterministic integration tests.
        # Customer-facing provider output always passes through the safety policy.
        safe_text = (
            response.text
            if response.provider == "mock"
            else self._response_policy.sanitize(response.text, fallback=_SAFE_FALLBACK)
        )
        if scope.kind == "mixed" and scope.customer_message is not None:
            safe_text = f"{scope.customer_message}\n\n{safe_text}"
        if self._memory is not None and conversation_key is not None:
            self._memory.record(conversation_key, user_message, safe_text, selected_sku)
        return LLMResponse(text=safe_text, provider=response.provider, model=response.model)

    async def aclose(self) -> None:
        await self._llm.aclose()
