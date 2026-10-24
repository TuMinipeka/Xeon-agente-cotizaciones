from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from evals.checks import EvalView, run_check
from evals.reference.oracle import FixtureMismatch, Oracle
from scripts.export_eval_fixtures import export


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
