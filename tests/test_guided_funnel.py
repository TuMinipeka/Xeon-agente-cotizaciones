"""Deterministic D14 journeys and Kapso interactive contract doubles."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from xeon.adapters.channels.kapso import KapsoChannelAdapter, parse_kapso_webhook
from xeon.adapters.policies.yaml_store import YamlPolicyRepository
from xeon.api.app import create_app
from xeon.application.container import build_container
from xeon.application.reply import Option, Reply
from xeon.config import Settings
from xeon.domain.quote import QuoteStatus


def _guided_container():  # type: ignore[no-untyped-def]
    return build_container(Settings(llm_provider="mock", _env_file=None))


def test_button_journey_confirms_customer_without_approval() -> None:
    async def run() -> None:
        container = _guided_container()
        key = "guided-buttons"
        try:
            path = (
                ("start:products", "producto"),
                ("cemento gris 50kg", "producto"),
                ("product:CEM-50", "cantidad"),
                ("quantity:10", "mas"),
                ("more:view", "entrega"),
                ("delivery:pickup", "sede"),
                ("branch:sede-norte", "pago"),
                ("payment:0", "resumen"),
                ("summary:confirm", "confirmado"),
            )
            reply = None
            for message, expected_step in path:
                reply = await container.agent.respond_reply(message, conversation_key=key)
                assert reply.step == expected_step
            assert reply is not None
            assert "asesor" in reply.text
            assert "289.000" in container.agent._funnel._cart(key)  # type: ignore[union-attr]
            assert any(
                quote.status is QuoteStatus.CONFIRMADO_POR_CLIENTE
                for quote in container.quotes._quotes.values()  # type: ignore[attr-defined]
            )
        finally:
            await container.aclose()

    asyncio.run(run())


def test_numbered_text_and_unrelated_redirect() -> None:
    async def run() -> None:
        container = _guided_container()
        try:
            first = await container.agent.respond_reply("1", conversation_key="guided-text")
            assert first.step == "producto"
            search = await container.agent.respond_reply(
                "cemento gris", conversation_key="guided-text"
            )
            assert search.options[0].id.startswith("product:")
            picked = await container.agent.respond_reply("1", conversation_key="guided-text")
            assert picked.step == "cantidad"
            amount = await container.agent.respond_reply("10", conversation_key="guided-text")
            assert amount.step == "mas"
            unrelated = await container.agent.respond_reply(
                "cuentame un chiste", conversation_key="guided-text"
            )
            assert unrelated.step == "mas"
            assert unrelated.text.startswith("Solo puedo ayudarte con tu cotización.")
        finally:
            await container.aclose()

    asyncio.run(run())


def test_text_choices_through_every_step_and_cart_edit() -> None:
    async def run() -> None:
        container = _guided_container()
        key = "guided-free-text"
        try:
            assert (
                await container.agent.respond_reply("Cotizar productos", conversation_key=key)
            ).step == "producto"
            products = await container.agent.respond_reply(
                "cemento gris 50kg", conversation_key=key
            )
            assert products.step == "producto"
            chosen = await container.agent.respond_reply(
                products.options[0].title, conversation_key=key
            )
            assert chosen.step == "cantidad"
            assert (await container.agent.respond_reply("10", conversation_key=key)).step == "mas"
            edited = await container.agent.respond_reply("dejalo en 15", conversation_key=key)
            assert edited.step == "mas"
            assert "15" in container.agent._funnel._cart(key)  # type: ignore[union-attr]
            assert (
                await container.agent.respond_reply("Ver cotizacion", conversation_key=key)
            ).step == "entrega"
            assert (
                await container.agent.respond_reply("Recoger en sede", conversation_key=key)
            ).step == "sede"
            branch_options = await container.agent.respond_reply("otro tema", conversation_key=key)
            assert branch_options.step == "sede"
            branch = next(item for item in branch_options.options if item.id == "branch:sede-norte")
            assert (
                await container.agent.respond_reply(branch.title, conversation_key=key)
            ).step == "pago"
            assert (
                await container.agent.respond_reply("Efectivo", conversation_key=key)
            ).step == "resumen"
            # Irreversible options are not reachable by title text (review M7); the id is.
            assert (
                await container.agent.respond_reply("Confirmar", conversation_key=key)
            ).step == "resumen"
            assert (
                await container.agent.respond_reply("summary:confirm", conversation_key=key)
            ).step == "confirmado"
        finally:
            await container.aclose()

    asyncio.run(run())


def test_reply_limits_and_null_policy(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Reply("elige", kind="buttons", options=tuple(Option(str(i), str(i)) for i in range(4)))
    with pytest.raises(ValueError):
        Reply("elige", kind="buttons", options=(Option("a", "x" * 21),))
    with pytest.raises(ValueError):
        Reply("elige", kind="list", options=tuple(Option(str(i), str(i)) for i in range(11)))
    with pytest.raises(ValueError):
        Reply("elige", kind="list", options=(Option("a", "x" * 25),))
    (tmp_path / "store.yaml").write_text(
        "demo: false\nhorario: {domingo: null}\n", encoding="utf-8"
    )
    policy = YamlPolicyRepository(tmp_path)
    assert policy.load("store").horario is not None
    assert policy.load("store").horario.domingo is None
    assert policy.get("store", "horarios") is None


def test_kapso_interactive_payload_and_webhook_replies() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.test"}]})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = KapsoChannelAdapter(
                base_url="https://api.kapso.ai",
                phone_number_id="123",
                graph_version="v24.0",
                api_key="test-only",
                client=client,
            )
            await adapter.send_reply(
                recipient_number="573001112233",
                reply=Reply("Elige", kind="buttons", options=(Option("yes", "Sí"),)),
            )
            await adapter.send_reply(
                recipient_number="573001112233",
                reply=Reply("Elige", kind="list", options=(Option("branch:north", "Norte"),)),
            )

    asyncio.run(run())
    assert captured[0]["interactive"]["type"] == "button"  # type: ignore[index]
    assert captured[0]["interactive"]["action"]["buttons"][0]["reply"]["id"] == "yes"  # type: ignore[index]
    assert captured[1]["interactive"]["type"] == "list"  # type: ignore[index]
    assert captured[1]["interactive"]["action"]["sections"][0]["rows"][0]["id"] == "branch:north"  # type: ignore[index]
    for reply_type in ("button_reply", "list_reply"):
        payload = {
            "phone_number_id": "123",
            "conversation": {"phone_number": "573001112233"},
            "message": {
                "id": "wamid.in",
                "type": "interactive",
                "interactive": {reply_type: {"id": "yes", "title": "Sí"}},
            },
        }
        incoming = parse_kapso_webhook(payload)
        assert incoming is not None and incoming.option_id == "yes"


def test_kapso_three_choice_steps_use_three_reply_buttons() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.start"}]})

    async def run() -> list[tuple[str, ...]]:
        container = _guided_container()
        try:
            key = "three-buttons"
            replies = [await container.agent.respond_reply("hola", conversation_key=key)]
            for message in (
                "start:products",
                "cemento",
                "product:CEM-50",
                "quantity:10",
                "more:view",
                "delivery:pickup",
                "branch:sede-norte",
                "payment:0",
            ):
                replies.append(await container.agent.respond_reply(message, conversation_key=key))
            selected = [
                reply
                for reply in replies
                if reply.step in {"inicio", "cantidad", "mas", "entrega", "resumen"}
            ]
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                adapter = KapsoChannelAdapter(
                    base_url="https://api.kapso.ai",
                    phone_number_id="123",
                    graph_version="v24.0",
                    api_key="test-only",
                    client=client,
                )
                for reply in selected:
                    assert reply.kind == "buttons"
                    assert len(reply.options) == 3
                    await adapter.send_reply(recipient_number="573001112233", reply=reply)
            return [tuple(option.id for option in reply.options) for reply in selected]
        finally:
            await container.aclose()

    option_ids = asyncio.run(run())
    assert len(sent) == len(option_ids) == 5
    for payload, expected in zip(sent, option_ids, strict=True):
        assert payload["type"] == "interactive"
        interactive = payload["interactive"]
        assert interactive["type"] == "button"
        buttons = interactive["action"]["buttons"]
        assert len(buttons) == 3
        assert tuple(button["reply"]["id"] for button in buttons) == expected
    assert option_ids[-1] == ("summary:confirm", "summary:modify", "global:cancel")


def test_guided_chat_returns_step_and_numbered_options() -> None:
    async def run() -> None:
        app = create_app(settings=Settings(llm_provider="mock", _env_file=None))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://xeon.local"
        ) as client:
            response = await client.post("/v1/chat", json={"message": "Cotizar productos"})
            assert response.status_code == 200
            payload = response.json()
            assert payload["step"] == "producto"
            assert payload["options"] == []
            assert "¿Qué producto buscas?" in payload["reply"]

    asyncio.run(run())


@pytest.mark.parametrize(
    ("query", "sku", "expected"),
    [
        ("cemento", "CEM-50", ("quantity:10", "quantity:20", "quantity:other")),
        (
            "pala redonda mango de fibra",
            "PAL-RED-FIB",
            ("quantity:1", "quantity:2", "quantity:other"),
        ),
        ("alambre de pua", "ALA-14", ("quantity:10", "quantity:50", "quantity:other")),
    ],
)
def test_quantity_names_product_and_suggests_its_unit(
    query: str, sku: str, expected: tuple[str, ...]
) -> None:
    async def run() -> None:
        container = _guided_container()
        try:
            key = f"quantity-{sku}"
            await container.agent.respond_reply("start:products", conversation_key=key)
            await container.agent.respond_reply(query, conversation_key=key)
            reply = await container.agent.respond_reply(f"product:{sku}", conversation_key=key)
            product = container.catalog.find_exact(sku)
            assert product is not None
            assert f"¿Cuántas unidades de {product.name}?" in reply.text
            assert tuple(option.id for option in reply.options) == expected
            assert reply.kind == "buttons"
            added = await container.agent.respond_reply(expected[0], conversation_key=key)
            assert added.step == "mas"
            cart = container.carts.get(key)
            assert cart is not None and cart.confirmed_lines()[0].quantity == int(
                expected[0].split(":")[1]
            )
        finally:
            await container.aclose()

    asyncio.run(run())


def test_policy_questions_keep_step_and_options_and_use_tenant_yaml(tmp_path: Path) -> None:
    (tmp_path / "store.yaml").write_text(
        "demo: false\npagos: [Efectivo, Transferencia]\n"
        "entrega: {recoger_en_sede: {disponible: true, nota: Hoy}, "
        "domicilio: {disponible: true, costo: null}}\n"
        "horario: {lunes_a_viernes: '8:00-17:00', sabado: null, domingo: null}\n"
        "vigencia_cotizacion_dias: null\niva: null\ndescuentos: null\n",
        encoding="utf-8",
    )

    async def run() -> None:
        container = build_container(
            Settings(llm_provider="mock", tenant_id="store", _env_file=None),
            policies=YamlPolicyRepository(tmp_path),
        )
        try:
            key = "policy-any-step"
            cases = (
                (
                    "¿Cuál es el horario del domingo?",
                    "Horario:",
                    "domingo: pendiente de confirmar con un asesor",
                ),
                ("¿Hacen domicilio?", "Domicilio:", "pendiente de confirmar con un asesor"),
                ("¿Cómo puedo pagar?", "Medios de pago:", "Transferencia"),
                ("¿El precio incluye IVA?", "IVA:", "pendiente de confirmar con un asesor"),
                (
                    "¿Hay descuento?",
                    "Politica de descuentos:",
                    "pendiente de confirmar con un asesor",
                ),
                ("¿Cuál es la vigencia?", "Vigencia:", "pendiente de confirmar con un asesor"),
                ("¿Puedo recoger en sede?", "Recogida en sede:", "Hoy"),
            )
            before = await container.agent.respond_reply("hola", conversation_key=key)
            for question, label, detail in cases:
                reply = await container.agent.respond_reply(question, conversation_key=key)
                assert reply.step == before.step
                assert reply.options == before.options
                assert label in reply.text and detail in reply.text
                assert "Solo puedo ayudarte" not in reply.text
            await container.agent.respond_reply("start:products", conversation_key=key)
            before = await container.agent.respond_reply("cemento", conversation_key=key)
            reply = await container.agent.respond_reply(
                "¿Qué medios de pago hay?", conversation_key=key
            )
            assert reply.step == "producto" and reply.options == before.options
            await container.agent.respond_reply("product:CEM-50", conversation_key=key)
            before = await container.agent.respond_reply(
                "¿Cuál es la vigencia?", conversation_key=key
            )
            assert before.step == "cantidad"
            assert tuple(item.id for item in before.options) == (
                "quantity:10",
                "quantity:20",
                "quantity:other",
            )
            await container.agent.respond_reply("quantity:10", conversation_key=key)
            reply = await container.agent.respond_reply("¿Hacen domicilio?", conversation_key=key)
            assert reply.step == "mas" and len(reply.options) == 3
            await container.agent.respond_reply("more:view", conversation_key=key)
            for step, question, next_choice in (
                ("entrega", "¿Hay descuento?", "delivery:pickup"),
                ("sede", "¿El precio incluye IVA?", "branch:sede-norte"),
                ("pago", "¿Cuál es el horario?", "payment:0"),
                ("resumen", "¿Cuántos días de vigencia tiene?", None),
            ):
                before = container.agent._funnel.render(key)
                reply = await container.agent.respond_reply(question, conversation_key=key)
                assert reply.step == step and reply.options == before.options
                assert "pendiente de confirmar con un asesor" in reply.text
                assert "Solo puedo ayudarte" not in reply.text
                if next_choice:
                    await container.agent.respond_reply(next_choice, conversation_key=key)
            cancelled = await container.agent.respond_reply("global:cancel", conversation_key=key)
            assert cancelled.step == "cancelado"
        finally:
            await container.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("command", "expected_step"),
    [("global:cancel", "cancelado"), ("asesor", "asesor")],
)
def test_global_text_commands_work_without_occupying_quantity_buttons(
    command: str, expected_step: str
) -> None:
    async def run() -> None:
        container = _guided_container()
        try:
            key = f"global-{command}"
            await container.agent.respond_reply("start:products", conversation_key=key)
            await container.agent.respond_reply("cemento", conversation_key=key)
            quantity = await container.agent.respond_reply("product:CEM-50", conversation_key=key)
            assert all(not option.id.startswith("global:") for option in quantity.options)
            reply = await container.agent.respond_reply(command, conversation_key=key)
            assert reply.step == expected_step
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s15_compound_weight_question_uses_verified_catalog_presentation() -> None:
    async def run() -> None:
        container = _guided_container()
        key = "s15-guided"
        try:
            for message in ("start:products", "cemento", "product:CEM-50", "quantity:10"):
                await container.agent.respond_reply(message, conversation_key=key)
            reply = await container.agent.respond_reply(
                "¿También manejan arena y gravilla? "
                "¿Cuántos kilos trae un bulto y el domicilio es gratis?",
                conversation_key=key,
            )
            assert "50 kg" in reply.text
            assert "Domicilio:" in reply.text
            assert "lo confirma un asesor" in reply.text
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s16_adjustment_shows_subtotal_and_thanks_keeps_cart() -> None:
    async def run() -> None:
        container = _guided_container()
        key = "s16-guided"
        try:
            for message in ("start:products", "cemento", "product:CEM-50", "quantity:20"):
                await container.agent.respond_reply(message, conversation_key=key)
            adjusted = await container.agent.respond_reply(
                "Mejor déjamelo en 15 bultos.", conversation_key=key
            )
            assert adjusted.step == "mas"
            assert "$433.500" in adjusted.text
            closed = await container.agent.respond_reply("ok gracias", conversation_key=key)
            assert closed.step == "mas"
            assert "$433.500" in closed.text
            assert "¡Hola!" not in closed.text
            cart = container.carts.get(key)
            assert cart is not None and cart.confirmed_lines()[0].quantity == 15
        finally:
            await container.aclose()

    asyncio.run(run())


def test_s19_whole_surface_answer_is_not_reasked() -> None:
    async def run() -> None:
        container = _guided_container()
        key = "s19-guided"
        try:
            await container.agent.respond_reply("start:project", conversation_key=key)
            reply = await container.agent.respond_reply(
                "toda la superficie 20x30 dame lista materiales corral ganado "
                "no preguntes mas medidas",
                conversation_key=key,
            )
            assert "600 m²" in reply.text
            assert "Toda la superficie confirmada" in reply.text
            assert "¿Se trabajará toda la superficie" not in reply.text
            repeat = await container.agent.respond_reply("toda la superficie", conversation_key=key)
            assert "¿Se trabajará toda la superficie" not in repeat.text
        finally:
            await container.aclose()

    asyncio.run(run())
