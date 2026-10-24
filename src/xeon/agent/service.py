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
        previous_sku = (
            self._memory.last_sku(conversation_key)
            if self._memory is not None and conversation_key is not None
            else None
        )
        pending = (
            self._memory.pending_candidates(conversation_key)
            if self._memory is not None and conversation_key is not None
            else None
        )
        active = (
            self._memory.commercial_active(conversation_key)
            if self._memory is not None and conversation_key is not None
            else False
        )
        scope = self._scope_policy.classify(
            user_message,
            commercial_context=active or previous_sku is not None or pending is not None,
        )
        if scope.kind == "out_of_scope":
            return LLMResponse(
                text=scope.customer_message or _SAFE_FALLBACK,
                provider="local-policy",
                model="commercial-scope-v1",
            )

        if (
            self._memory is not None
            and conversation_key is not None
            and scope.kind in {"commercial", "mixed"}
        ):
            self._memory.mark_commercial(conversation_key)

        commercial_message = scope.commercial_query or user_message
        message_list: list[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
        ]
        selected_sku: str | None = None
        if self._tools is not None:
            known_lines = (
                self._memory.resolved_lines(conversation_key)
                if self._memory is not None and conversation_key is not None
                else ()
            )
            fallback_quantity = (
                self._memory.unresolved_quantity(conversation_key)
                if self._memory is not None and conversation_key is not None
                else None
            )
            verified_context, selected_sku, new_pending, resolved_lines = (
                self._tools.prepare_verified_context(
                    commercial_message,
                    request_id=request_id,
                    last_sku=previous_sku,
                    pending=pending,
                    known_lines=known_lines,
                    fallback_quantity=fallback_quantity,
                )
            )
            if verified_context is not None:
                message_list.append(ChatMessage(role="system", content=verified_context))
            if self._memory is not None and conversation_key is not None:
                if new_pending is not None:
                    self._memory.set_pending_candidates(conversation_key, new_pending)
                    if new_pending.quantity is not None:
                        self._memory.remember_unresolved_quantity(
                            conversation_key, new_pending.quantity
                        )
                elif selected_sku is not None:
                    self._memory.set_pending_candidates(conversation_key, None)
                if resolved_lines:
                    self._memory.remember_lines(conversation_key, resolved_lines)
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
