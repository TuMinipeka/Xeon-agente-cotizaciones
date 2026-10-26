"""The intent boundary preserves every commercial request in a mixed turn."""

from decimal import Decimal

from xeon.agent.intent import IntentKind, fallback_intents
from xeon.application.ports.conversation_memory import PendingCandidates


def _kinds(message: str) -> tuple[IntentKind, ...]:
    return tuple(item.kind for item in fallback_intents(message).intents)


def test_unrelated_request_is_outside_without_a_commercial_intent() -> None:
    assert _kinds("Busca tarjetas gráficas para jugar y pásame enlaces") == (
        IntentKind.FUERA_DE_ALCANCE,
    )


def test_greeting_and_hardware_categories_remain_commercial() -> None:
    assert _kinds("hola") == (IntentKind.SALUDO,)
    for message in (
        "Necesito cemento para construcción",
        "Busco una herramienta para el taller",
        "Necesito tubería para plomería",
        "Busco cable para electricidad",
        "Necesito alambre para el potrero",
    ):
        assert IntentKind.FUERA_DE_ALCANCE not in _kinds(message)


def test_mixed_request_preserves_commercial_part_without_rejection_prefix() -> None:
    batch = fallback_intents("Necesito cemento y busca tarjetas gráficas con enlaces")
    assert tuple(item.kind for item in batch.intents) == (
        IntentKind.AGREGAR,
        IntentKind.FUERA_DE_ALCANCE,
    )
    assert batch.intents[0].source_text == "Necesito cemento"


def test_short_choice_uses_pending_options() -> None:
    pending = PendingCandidates(
        skus=("CEM-50", "SYN-CEM-0001"),
        names=("Cemento gris 50 kg", "Cemento gris referencia sintética 1"),
        quantity=Decimal(10),
        branch="",
    )
    assert fallback_intents("La primera opción", pending=pending).intents[0].kind is (
        IntentKind.ELEGIR_OPCION
    )


def test_logistics_and_multiple_questions_are_not_outside() -> None:
    for message in (
        "10 bultos de cemento y entrega en sede sur",
        "Lo recojo en la sede norte",
        "¿Qué opciones tengo para pagar y recoger?",
    ):
        assert IntentKind.FUERA_DE_ALCANCE not in _kinds(message)


def test_poem_and_cement_turn_keeps_sale_without_rejection_prefix() -> None:
    batch = fallback_intents("escribieme un poema de la lluvia y cuanto valen 4 bultos de cemento")
    assert IntentKind.FUERA_DE_ALCANCE in _kinds(batch.intents[0].source_text)
    assert any(intent.kind is IntentKind.AGREGAR for intent in batch.intents)
