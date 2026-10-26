from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal

from xeon.adapters.conversation.memory import InMemoryConversationMemory
from xeon.agent.intent import IntentInterpreter, IntentKind, fallback_intents
from xeon.agent.toolbelt import _pending_selection
from xeon.application.ports.conversation_memory import PendingCandidates, ProjectContext
from xeon.application.ports.llm import ChatMessage, LLMResponse


class JsonLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "test-json"

    @property
    def model(self) -> str:
        return "local-stub"

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        self.calls += 1
        assert messages[-1].role == "user"
        return LLMResponse(text=self.text, provider=self.provider_name, model=self.model)

    async def aclose(self) -> None:
        return None


def test_fallback_handles_all_requests_and_does_not_mutate_hypothetical_intent() -> None:
    batch = fallback_intents("cámbialo a 15 y deja dos palas")
    assert [intent.kind for intent in batch.intents] == [
        IntentKind.MODIFICAR_CANTIDAD,
        IntentKind.AGREGAR,
    ]
    assert [intent.quantity for intent in batch.intents] == [Decimal(15), Decimal(2)]
    assert (
        fallback_intents("¿Qué descuento hay por 50 bultos?").intents[0].kind
        is IntentKind.HIPOTETICA
    )
    policies = fallback_intents("¿Qué opciones tengo para pagar y recoger mi pedido?")
    assert [intent.policy for intent in policies.intents] == ["pagos", "recogida"]


def test_pending_question_resolves_short_attribute_reply_and_project_area() -> None:
    pending = PendingCandidates(
        ("PAL-RED-FIB", "PAL-CUA-MAD"),
        ("Pala redonda mango de fibra", "Pala cuadrada mango de madera"),
        Decimal(1),
        "sede-norte",
        ({"forma": "redonda", "mango": "fibra"}, {"forma": "cuadrada", "mango": "madera"}),
    )
    assert _pending_selection("redonda con mango de fibra", pending) == "PAL-RED-FIB"
    assert (
        fallback_intents("redonda con mango de fibra", pending=pending).intents[0].kind
        is IntentKind.ELEGIR_OPCION
    )
    project_message = "Necesito materiales para un corral de 20 \u00d7 30 metros"
    project = fallback_intents(project_message).intents[0].project
    assert project is not None
    memory = InMemoryConversationMemory()
    memory.remember_project_data(
        "corral", ProjectContext(project.length_m, project.width_m, project.purpose)
    )
    assert memory.project_data("corral").area_m2 == Decimal(600)


def test_model_json_is_validated_once_then_bad_json_uses_fallback() -> None:
    valid = JsonLLM('{"intents":[{"kind":"ver_resumen_total","source_text":"resumen"}]}')
    batch, _ = asyncio.run(IntentInterpreter().interpret("Resúmeme mi cotización", llm=valid))
    assert valid.calls == 1
    assert batch.intents[0].kind is IntentKind.VER_RESUMEN_TOTAL
    invalid = JsonLLM("respuesta libre sin JSON")
    batch, _ = asyncio.run(IntentInterpreter().interpret("Resúmeme mi cotización", llm=invalid))
    assert invalid.calls == 1
    assert batch.intents[0].kind is IntentKind.VER_RESUMEN_TOTAL
