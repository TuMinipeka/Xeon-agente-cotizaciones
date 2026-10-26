"""Single commercial conversation path: interpret, execute, and render."""

from __future__ import annotations

from xeon.agent.customer_safety import CustomerResponsePolicy
from xeon.agent.executor import CommercialExecutor
from xeon.agent.intent import IntentInterpreter, IntentKind
from xeon.application.ports.conversation_memory import ConversationMemory
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMResponse


class AgentService:
    def __init__(
        self,
        llm: LLMPort,
        *,
        memory: ConversationMemory,
        executor: CommercialExecutor,
        response_policy: CustomerResponsePolicy | None = None,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._executor = executor
        self._interpreter = IntentInterpreter()
        self._response_policy = response_policy or CustomerResponsePolicy()

    async def respond(
        self,
        user_message: str,
        *,
        conversation_key: str | None = None,
        request_id: str | None = None,
    ) -> LLMResponse:
        key = conversation_key or "anonymous"
        pending = self._memory.pending_candidates(key)
        history = tuple(
            ChatMessage(
                role=entry.role,
                content=entry.content.split("\n[XEON_TOOL:", 1)[0]
                if entry.role == "assistant"
                else entry.content,
            )
            for entry in self._memory.history(key)
        )
        batch, model_response = await self._interpreter.interpret(
            user_message,
            llm=self._llm,
            pending=pending,
            context=self._executor.interpreter_context(key),
            history=history,
        )
        outside_only = all(intent.kind is IntentKind.FUERA_DE_ALCANCE for intent in batch.intents)
        result = self._executor.execute(
            batch, message=user_message, conversation_key=key, request_id=request_id
        )
        rendered = result.text
        transactional = any(
            intent.kind
            in {
                IntentKind.AGREGAR,
                IntentKind.MODIFICAR_CANTIDAD,
                IntentKind.QUITAR,
                IntentKind.ELEGIR_OPCION,
                IntentKind.RESPONDER_PENDIENTE,
            }
            for intent in batch.intents
        )
        if result.advice_requested and not transactional and self._llm.provider_name != "mock":
            project = self._memory.project_data(key)
            area = str(project.area_m2) if project.area_m2 is not None else "no confirmada"
            advice = await self._llm.complete(
                (
                    ChatMessage(
                        role="system",
                        content=(
                            "Redacta una orientacion breve para un proyecto de ferreteria. "
                            "La superficie informada es " + area + " m2. "
                            "No calcules cantidades, precios ni stock. "
                            "Es una lista preliminar que requiere validacion tecnica."
                        ),
                    ),
                    ChatMessage(role="user", content=user_message),
                )
            )
            safe_advice = self._response_policy.sanitize(advice.text, fallback="")
            if safe_advice:
                rendered += "\n" + safe_advice
        if self._llm.provider_name == "mock" and result.diagnostics:
            rendered += "\n" + "\n".join(result.diagnostics)
        self._memory.record(key, user_message, rendered, result.selected_sku)
        return LLMResponse(
            text=rendered,
            provider=(
                "local-policy"
                if outside_only
                else model_response.provider
                if model_response
                else self._llm.provider_name
            ),
            model=(
                "commercial-scope-v2"
                if outside_only
                else model_response.model
                if model_response
                else self._llm.model
            ),
        )

    async def aclose(self) -> None:
        await self._llm.aclose()
