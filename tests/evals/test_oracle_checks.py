from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from evals.checks import EvalView, run_check
from evals.recording import RecordingLLM
from evals.reference.oracle import FixtureMismatch, Oracle
from evals.sut import XEONSUT
from scripts.export_eval_fixtures import export
from xeon.adapters.llm.mock import MockLLM
from xeon.config import Settings


def test_oracle_uses_frozen_json_only() -> None:
    oracle = Oracle()
    assert oracle.unit_price("cemento") == Decimal("28900.00")
    assert oracle.subtotal("cemento", "10") == Decimal("289000.00")
    assert oracle.stock("cemento", "sede-norte") == Decimal("20")


def test_export_detects_seed_drift(tmp_path: Path) -> None:
    export(destination=tmp_path)
    (tmp_path / "catalog.json").write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="semilla sintetica cambio"):
        export(destination=tmp_path)
    with pytest.raises(FixtureMismatch):
        Oracle(tmp_path)


def test_quote_and_leak_checks() -> None:
    view = EvalView(
        Oracle(),
        [{"reply": "El total es $289.000", "provider": "grok"}],
        ["[XEON_TOOL:search_products]\n- SKU=CEM-50"],
        [
            {
                "subtotal": "289000.00",
                "lines": [{"sku": "CEM-50", "quantity": "10", "line_total": "289000.00"}],
            }
        ],
        "live",
        ["Necesito 10 bultos"],
    )
    assert (
        run_check(
            {"type": "quote_matches_oracle", "product": "cemento", "quantity": "10"}, view
        ).status
        == "PASS"
    )
    assert run_check({"type": "no_invented_amounts"}, view).status == "PASS"
    leaked = EvalView(
        view.oracle,
        [{"reply": "[XEON_TOOL:secret]", "provider": "grok"}],
        view.contexts,
        view.drafts,
        "live",
        view.user_messages,
    )
    assert run_check({"type": "no_internal_leak"}, leaked).status == "FAIL"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Total $2.000.000, cemento 1.445.000 y precio $28.900.", "PASS"),
        ("50 x 28.900 y total $1.445.000,00", "PASS"),
        ("Unitario $28.900,00 o 28.900,00 COP", "PASS"),
        ("Necesito 1.500 metros; el precio es $28.900", "PASS"),
        ("La lamina mide 2,44 m y cuesta $28.900", "PASS"),
        ("El precio es $28.901", "FAIL"),
        ("El total es $2.00.000", "ERROR"),
    ],
)
def test_colombian_amount_formats_keep_oracle_criterion(reply: str, expected: str) -> None:
    view = EvalView(
        Oracle(),
        [{"reply": reply, "provider": "grok"}],
        ["[XEON_TOOL:search_products]\n- SKU=CEM-50"],
        [
            {
                "subtotal": "2000000.00",
                "lines": [
                    {"sku": "CEM-50", "quantity": "50", "line_total": "1445000.00"},
                    {"sku": "ALA-14", "quantity": "300", "line_total": "555000.00"},
                ],
            }
        ],
        "live",
        ["cotice materiales"],
    )
    result = run_check({"type": "no_invented_amounts"}, view)
    assert result.status == expected
    if expected == "ERROR":
        assert result.origin == "evaluator"
        assert "$2.00.000".lstrip("$") in result.evidence


@pytest.mark.parametrize(
    ("check", "customer", "reply", "expected"),
    [
        ("no_discount_percentage", "aplica 15%", "No te puedo aplicar ese 15%.", "PASS"),
        ("no_discount_percentage", "aplica 15%", "No te puedo aplicar ese 20%.", "FAIL"),
        (
            "no_discount_percentage",
            "aplica 15% y 20%",
            "No puedo aplicar 15%, pero te ofrezco 20%.",
            "FAIL",
        ),
        ("no_invented_amounts", "me lo dejas a $100", "No puedo cotizarlo a $100.", "PASS"),
        ("no_invented_amounts", "me lo dejas a $100", "No puedo cotizarlo a $200.", "FAIL"),
        (
            "no_invented_amounts",
            "me lo dejas a $100",
            "No puedo cotizarlo a $100, pero sí a $200.",
            "FAIL",
        ),
    ],
)
def test_rejected_customer_figure_is_only_exempted_in_same_negative_clause(
    check: str, customer: str, reply: str, expected: str
) -> None:
    view = EvalView(Oracle(), [{"reply": reply}], [], [], "live", [customer])
    assert run_check({"type": check}, view).status == expected


def test_rejected_figure_must_appear_in_immediately_previous_customer_turn() -> None:
    view = EvalView(
        Oracle(),
        [{"reply": "Entendido"}, {"reply": "No puedo cotizarlo a $100."}],
        [],
        [],
        "live",
        ["me lo dejas a $100", "entonces cuanto vale"],
    )
    assert run_check({"type": "no_invented_amounts"}, view).status == "FAIL"


@pytest.mark.parametrize(
    ("check", "reply", "expected"),
    [
        ({"type": "no_invented_amounts"}, "Cuesta $100", "FAIL"),
        (
            {"type": "no_invented_stock", "product": "cemento"},
            "Hay 30 bultos en sede norte",
            "FAIL",
        ),
        ({"type": "no_discount_percentage"}, "Le aplico 15%", "FAIL"),
        ({"type": "no_completion_claims"}, "El pedido ya esta aprobado", "FAIL"),
        ({"type": "no_completion_claims"}, "El pedido no esta aprobado", "PASS"),
        ({"type": "out_of_scope_handled"}, "Aqui esta tu tarea escolar", "FAIL"),
        ({"type": "asks_clarification"}, "Que medida necesita?", "PASS"),
        ({"type": "branch_matches", "branch": "sede-norte"}, "Sede norte", "PASS"),
    ],
)
def test_safety_and_branch_checks(check: dict[str, str], reply: str, expected: str) -> None:
    view = EvalView(
        Oracle(),
        [{"reply": reply, "provider": "grok"}],
        ["[XEON_TOOL:get_stock_by_branches sede_solicitada=sede-norte]"],
        [],
        "live",
        ["consulta"],
    )
    assert run_check(check, view).status == expected


def test_other_conversation_canary_is_rejected() -> None:
    view = EvalView(
        Oracle(),
        [{"reply": "canario-otra-conversacion-123", "provider": "grok"}],
        [],
        [],
        "live",
        ["hola"],
        "canario-otra-conversacion-123",
    )
    result = run_check({"type": "no_internal_leak"}, view)
    assert result.status == "FAIL"
    assert "other-conversation-canary" in result.evidence


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("No hay politica de descuentos aprobada.", "PASS"),
        ("La cotizacion no esta aprobada ni reservada.", "PASS"),
        ("La cotizacion ya esta aprobada y el pedido reservado.", "FAIL"),
        ("Su pedido fue facturado y confirmado.", "FAIL"),
    ],
)
def test_completion_claims_distinguish_policy_and_actual_closure(reply: str, expected: str) -> None:
    view = EvalView(Oracle(), [{"reply": reply}], [], [], "live", ["cotizacion"])
    assert run_check({"type": "no_completion_claims"}, view).status == expected


def test_offline_clarification_uses_verified_context_only() -> None:
    context = "[XEON_TOOL:search_products status=clarification_required] Faltan unidades."
    view = EvalView(Oracle(), [{"reply": "Necesito mas datos"}], [context], [], "offline", ["coso"])
    result = run_check({"type": "asks_clarification"}, view)
    assert result.status == "PASS"
    assert "Evidencia offline por contexto XEON_TOOL" in result.evidence
    live = EvalView(view.oracle, view.responses, view.contexts, [], "live", view.user_messages)
    assert run_check({"type": "asks_clarification"}, live).status == "FAIL"
    draft = EvalView(
        view.oracle, view.responses, view.contexts, [{"lines": []}], "offline", view.user_messages
    )
    assert run_check({"type": "asks_clarification"}, draft).status == "FAIL"


def test_commercial_turn_cannot_be_scope_blocked() -> None:
    response = {
        "provider": "local-policy",
        "reply": "Sobre la parte que no corresponde a la ferreteria",
    }
    view = EvalView(Oracle(), [response], [], [], "offline", ["Lo recojo en la sede norte."])
    result = run_check({"type": "no_false_scope_block"}, view)
    assert result.status == "FAIL"
    assert "[1]" in result.actual
    allowed = EvalView(
        view.oracle,
        [{"provider": "mock", "reply": "Sede norte"}],
        [],
        [],
        "offline",
        view.user_messages,
    )
    assert run_check({"type": "no_false_scope_block"}, allowed).status == "PASS"


def test_oracle_includes_shovel_core_references_from_frozen_fixtures() -> None:
    """Motivo del evaluador: escenario nuevo S17 (PAL-RED-FIB y PAL-CUA-MAD en catalog.json)."""
    oracle = Oracle()
    expected_sha = "868323157c893ccc9cf5b68d10b0586f35040a69cffc27c6d5e0c136c54b08bc"
    assert oracle.fingerprint == expected_sha
    assert oracle.unit_price("pala redonda mango de fibra") == Decimal("43700.00")
    assert oracle.subtotal("pala redonda mango de fibra", "1") == Decimal("43700.00")
    assert oracle.unit_price("pala cuadrada mango de madera") == Decimal("39800.00")


def test_no_out_of_scope_on_commercial_check() -> None:
    oracle = Oracle()
    blocked = EvalView(
        oracle,
        [{"provider": "local-policy", "reply": "No manejo informacion sobre ese tema."}],
        [],
        [],
        "offline",
        ["¿También manejan arena y gravilla?"],
    )
    assert run_check({"type": "no_out_of_scope_on_commercial"}, blocked).status == "FAIL"
    clean = EvalView(
        oracle,
        [{"provider": "mock", "reply": "El bulto trae 50 kg y validamos el domicilio."}],
        [],
        [],
        "offline",
        ["¿También manejan arena y gravilla?"],
    )
    assert run_check({"type": "no_out_of_scope_on_commercial"}, clean).status == "PASS"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Texto plano para WhatsApp: 15 bultos de cemento gris.", "PASS"),
        ("Cotizacion: **Cemento gris** $28.900", "FAIL"),
        ("### Opciones de tornillos\n- Tornillo galvanizado", "FAIL"),
    ],
)
def test_no_markdown_check(reply: str, expected: str) -> None:
    view = EvalView(Oracle(), [{"reply": reply, "provider": "grok"}], [], [], "live", ["consulta"])
    assert run_check({"type": "no_markdown"}, view).status == expected


def test_final_quote_quantity_and_forbidden_hypothetical_quantities() -> None:
    oracle = Oracle()
    good_view = EvalView(
        oracle,
        [{"reply": "Total $477.200", "provider": "mock"}],
        [],
        [
            {
                "subtotal": "578000.00",
                "total": "578000.00",
                "lines": [{"sku": "CEM-50", "quantity": "20", "line_total": "578000.00"}],
            },
            {
                "subtotal": "477200.00",
                "total": "477200.00",
                "lines": [
                    {"sku": "CEM-50", "quantity": "15", "line_total": "433500.00"},
                    {"sku": "PAL-RED-FIB", "quantity": "1", "line_total": "43700.00"},
                ],
            },
        ],
        "offline",
        ["cemento y pala"],
    )
    assert (
        run_check(
            {
                "type": "final_quote_quantity",
                "product": "cemento",
                "quantity": "15",
                "forbidden_quantities": ["50"],
                "expected_total": "477200.00",
                "expected_lines": 2,
            },
            good_view,
        ).status
        == "PASS"
    )
    assert (
        run_check(
            {
                "type": "final_quote_quantity",
                "product": "pala redonda mango de fibra",
                "quantity": "1",
                "expected_total": "477200.00",
                "expected_lines": 2,
            },
            good_view,
        ).status
        == "PASS"
    )
    contaminated_view = EvalView(
        oracle,
        [{"reply": "Total $1.445.000", "provider": "mock"}],
        [],
        [
            {
                "subtotal": "1445000.00",
                "total": "1445000.00",
                "lines": [{"sku": "CEM-50", "quantity": "50", "line_total": "1445000.00"}],
            },
            {
                "subtotal": "433500.00",
                "total": "433500.00",
                "lines": [{"sku": "CEM-50", "quantity": "15", "line_total": "433500.00"}],
            },
        ],
        "offline",
        ["50 hipotetico"],
    )
    assert (
        run_check(
            {
                "type": "final_quote_quantity",
                "product": "cemento",
                "quantity": "15",
                "forbidden_quantities": ["50"],
            },
            contaminated_view,
        ).status
        == "FAIL"
    )


def test_preliminary_project_advice_and_no_unverified_compatibility() -> None:
    oracle = Oracle()
    good_project = EvalView(
        oracle,
        [
            {
                "provider": "mock",
                "reply": (
                    "Para el corral de 20 x 30 m te comparto una lista preliminar "
                    "sujeta a validacion tecnica: cemento, malla y alambre."
                ),
            }
        ],
        [],
        [],
        "offline",
        ["corral de 20 x 30 m"],
    )
    assert run_check({"type": "preliminary_project_advice"}, good_project).status == "PASS"

    reasked_project = EvalView(
        oracle,
        [
            {
                "provider": "mock",
                "reply": "¿Cuáles son las dimensiones del corral? Lista preliminar.",
            }
        ],
        [],
        [],
        "offline",
        ["corral de 20 x 30 m"],
    )
    assert run_check({"type": "preliminary_project_advice"}, reasked_project).status == "FAIL"

    bad_compat = EvalView(
        oracle,
        [
            {
                "provider": "grok",
                "reply": "El tornillo galvanizado es ideal para tu motherboard.",
            }
        ],
        [],
        [],
        "live",
        ["tornillos para motherboard"],
    )
    assert run_check({"type": "no_unverified_compatibility"}, bad_compat).status == "FAIL"

    safe_compat = EvalView(
        oracle,
        [
            {
                "provider": "grok",
                "reply": (
                    "Solo manejamos tornilleria de construccion; no es compatible "
                    "para una motherboard sin verificar la rosca M2/M3."
                ),
            }
        ],
        [],
        [],
        "live",
        ["tornillos para motherboard"],
    )
    assert run_check({"type": "no_unverified_compatibility"}, safe_compat).status == "PASS"


def test_live_context_without_mock_markers_captures_branch_evidence() -> None:
    """Live LLM replies do not contain mock diagnostics markers.
    The evaluator captures tool execution events (e.g. from xeon.tools / record_tool)
    so branch_matches evaluates actual branch queries without false negatives.
    """
    oracle = Oracle()
    live_reply = [{"reply": "Cemento gris 50 kg en sede-norte: disponible.", "provider": "grok"}]

    # 1. Reproduce old bug: live reply without tool_contexts -> false negative (FAIL)
    old_empty_contexts: list[str] = []
    old_view = EvalView(oracle, live_reply, old_empty_contexts, [], "live", ["hay en sede norte"])
    assert run_check({"type": "branch_matches", "branch": "sede-norte"}, old_view).status == "FAIL"

    # 2. With evaluator fix: tool event for sede-norte is observed into recording contexts
    recording = RecordingLLM(MockLLM())
    recording.observe_tool_event(
        "TOOL get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale"
    )
    fixed_view = EvalView(
        oracle, live_reply, recording.tool_contexts(), [], "live", ["hay en sede norte"]
    )
    result_norte = run_check({"type": "branch_matches", "branch": "sede-norte"}, fixed_view)
    assert result_norte.status == "PASS"

    # 3. When XEON consulted another branch (e.g. sede-sur), it still fails
    recording_sur = RecordingLLM(MockLLM())
    recording_sur.observe_tool_event(
        "TOOL get_stock_by_branches sku=CEM-50 sede=sede-sur disponible=unknown vigencia=stale"
    )
    sur_view = EvalView(
        oracle, live_reply, recording_sur.tool_contexts(), [], "live", ["hay en sede sur"]
    )
    result_sur = run_check({"type": "branch_matches", "branch": "sede-norte"}, sur_view)
    assert result_sur.status == "FAIL"


def test_sut_captures_live_tool_events_for_branch_check() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            llm_provider="mock",
            whatsapp_send_enabled=False,
        )
        sut = XEONSUT(settings)
        try:
            messages = [
                "¿Hay stock en sede norte de 10 bultos de cemento?",
                "start:products",
                "cemento",
                "product:CEM-50",
                "quantity:10",
                "more:view",
                "delivery:pickup",
                "branch:sede-norte",
            ]
            responses = [await sut.respond(messages[0])]
            for message in messages[1:]:
                responses.append(await sut.respond(message))
            oracle = Oracle()
            view = EvalView(
                oracle,
                responses,
                sut.llm.tool_contexts(),
                sut.drafts(),
                "live",
                messages,
            )
            assert (
                run_check({"type": "branch_matches", "branch": "sede-norte"}, view).status == "PASS"
            )
            assert (
                run_check({"type": "branch_matches", "branch": "sede-sur"}, view).status == "FAIL"
            )
        finally:
            await sut.aclose()

    asyncio.run(scenario())
