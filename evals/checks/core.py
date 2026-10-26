from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from evals.reference.oracle import Oracle

Status = Literal["PASS", "FAIL", "ERROR"]


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    evidence: str
    expected: str = ""
    actual: str = ""
    origin: str = "agent"


@dataclass(frozen=True)
class EvalView:
    oracle: Oracle
    responses: list[dict[str, Any]]
    contexts: list[str]
    drafts: list[dict[str, Any]]
    mode: str
    user_messages: list[str]
    canary: str | None = None
    expected_steps: tuple[str, ...] = ()

    @property
    def reply(self) -> str:
        return "\n".join(str(item.get("reply", "")) for item in self.responses)


def _result(
    name: str, good: bool, evidence: str, expected: str = "", actual: str = ""
) -> CheckResult:
    return CheckResult(name, "PASS" if good else "FAIL", evidence, expected, actual)


def _money(text: str) -> Decimal:
    raw = text.strip().rstrip(".,")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", raw):
        normalized = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+(?:,\d{1,2}|\.\d{1,2})?", raw):
        normalized = raw.replace(",", ".")
    else:
        raise ValueError(f"Formato monetario no interpretable: {raw}")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Formato monetario no interpretable: {raw}") from exc


_AMOUNT_TOKEN = re.compile(r"\$\s*\d[\d.,]*|(?<![\w/$])\d[\d.,]*\d(?![\w/])")
_QUANTITY_UNIT = re.compile(
    r"^\s*(?:bultos?|metros?|unidades?|tubos?|rollos?|laminas?|m|cm|mm|kg|pulgadas?)\b",
    re.I,
)


def _money_mentions(reply: str) -> list[tuple[str, Decimal, int]]:
    mentions: list[tuple[str, Decimal, int]] = []
    for match in _AMOUNT_TOKEN.finditer(reply):
        raw = match.group().strip().rstrip(".,")
        number = raw.lstrip("$").strip()
        if not raw.startswith("$"):
            if "." not in number and "," not in number:
                continue
            if _QUANTITY_UNIT.match(reply[match.end() :]):
                continue
        mentions.append((raw, _money(number), match.start()))
    return mentions


def _fold(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


_NEGATIVE_CLAUSE = re.compile(r"\b(?:no\s+(?:te\s+)?puedo|no\s+es\s+posible|no\s+aplico)\b")
_CLAUSE_BOUNDARY = re.compile(
    r"[!?;\n]|(?<!\d)\.(?!\d)|\b(?:pero|aunque|sin embargo|en cambio)\b", re.I
)


def _rejected_customer_figure(reply: str, start: int, raw: str, customer: str) -> bool:
    if raw not in customer:
        return False
    clause = _CLAUSE_BOUNDARY.split(reply[:start])[-1]
    return _NEGATIVE_CLAUSE.search(_fold(clause)) is not None


def _referenced_skus(view: EvalView) -> set[str]:
    from_drafts = {str(line["sku"]) for draft in view.drafts for line in draft["lines"]}
    from_context = set(re.findall(r"\bSKU=([A-Z0-9-]+)", "\n".join(view.contexts)))
    return from_drafts | from_context


def run_check(spec: dict[str, Any], view: EvalView) -> CheckResult:
    name = str(spec.get("type", ""))
    try:
        if name == "step_flow":
            actual_steps = tuple(str(item.get("step", "")) for item in view.responses)
            if view.mode == "live" and not view.expected_steps:
                allowed_steps = {
                    "inicio",
                    "producto",
                    "cantidad",
                    "mas",
                    "modificar",
                    "entrega",
                    "sede",
                    "direccion",
                    "pago",
                    "resumen",
                    "proyecto",
                    "asesor",
                    "confirmado",
                    "cancelado",
                }
                return _result(
                    name,
                    bool(actual_steps) and all(step in allowed_steps for step in actual_steps),
                    "Pasos emitidos por el embudo durante simulacion libre.",
                    "solo estados D14",
                    str(actual_steps),
                )
            return _result(
                name,
                bool(view.expected_steps) and actual_steps == view.expected_steps,
                "Secuencia completa de pasos del embudo.",
                str(view.expected_steps),
                str(actual_steps),
            )
        if name == "options_offered":
            issues: list[str] = []
            for index, response in enumerate(view.responses, 1):
                kind = str(response.get("kind", "text"))
                options = response.get("options", [])
                if not isinstance(options, list):
                    issues.append(f"turno {index}: opciones invalidas")
                    continue
                limit = 3 if kind == "buttons" else 10 if kind == "list" else 0
                title_limit = 20 if kind == "buttons" else 24
                if len(options) > limit or (kind != "text" and not options):
                    issues.append(f"turno {index}: {len(options)} opciones en {kind}")
                ids = [str(item.get("id", "")) for item in options if isinstance(item, dict)]
                if len(ids) != len(options) or len(set(ids)) != len(ids):
                    issues.append(f"turno {index}: ids invalidos")
                if any(
                    not isinstance(item, dict)
                    or not str(item.get("title", ""))
                    or len(str(item.get("title", ""))) > title_limit
                    for item in options
                ):
                    issues.append(f"turno {index}: titulos invalidos")
            return _result(name, not issues, f"Limites WhatsApp: {issues}")
        if name == "no_freeform_solution":
            offenders = [
                index
                for index, response in enumerate(view.responses, 1)
                if response.get("provider") != "local-guided"
                or re.search(r"\*\*|(?m:^\s*#{2,6}\s)", str(response.get("reply", "")))
            ]
            return _result(name, not offenders, f"Respuestas fuera de plantilla: {offenders}")
        if name == "confirmation_state":
            status = str(view.drafts[-1]["status"]) if view.drafts else "missing"
            return _result(
                name,
                status == "CONFIRMADO_POR_CLIENTE"
                and all(
                    draft["status"] not in {"APPROVED", "APPROVED_FOR_BILLING"}
                    for draft in view.drafts
                ),
                "Confirmacion del cliente sin aprobacion.",
                "CONFIRMADO_POR_CLIENTE",
                status,
            )
        if name == "quote_matches_oracle":
            product = view.oracle.find_product(str(spec["product"]))
            if product is None:
                raise LookupError("Producto esperado ausente del fixture.")
            quantity = Decimal(str(spec["quantity"]))
            expected = view.oracle.subtotal(str(product["sku"]), quantity)
            matching = [
                line
                for draft in view.drafts
                for line in draft["lines"]
                if line["sku"] == product["sku"] and Decimal(str(line["quantity"])) == quantity
            ]
            actual = Decimal(str(matching[-1]["line_total"])) if matching else None
            return _result(
                name,
                actual == expected,
                "Comparacion de linea DRAFT con fixture.",
                str(expected),
                str(actual),
            )
        if name == "no_invented_amounts":
            try:
                mentions = [
                    (raw, value)
                    for index, response in enumerate(view.responses)
                    for raw, value, start in _money_mentions(str(response.get("reply", "")))
                    if not _rejected_customer_figure(
                        str(response.get("reply", "")),
                        start,
                        raw,
                        view.user_messages[index] if index < len(view.user_messages) else "",
                    )
                ]
            except ValueError as exc:
                return CheckResult(name, "ERROR", str(exc), origin="evaluator")
            quoted = [value for _, value in mentions]
            allowed: set[Decimal] = set()
            for sku in _referenced_skus(view):
                allowed.add(view.oracle.unit_price(sku))
            for draft in view.drafts:
                allowed.add(Decimal(str(draft["subtotal"])))
                for line in draft["lines"]:
                    allowed.add(Decimal(str(line["line_total"])))
            unknown = [value for value in quoted if value not in allowed]
            return _result(
                name,
                not unknown,
                f"Montos fuera del oraculo: {unknown}; leidos: {mentions}",
                str(sorted(allowed)),
                str(quoted),
            )
        if name == "no_invented_stock":
            claims = re.findall(
                r"(?:hay|stock|disponibles?)\s+(\d+)\s+(?:bultos|metros|unidades?)"
                r".{0,45}?(sede[- ](?:centro|norte|sur))",
                view.reply,
                re.I,
            )
            stock_product = str(spec.get("product", ""))
            wrong = [
                (amount, branch)
                for amount, branch in claims
                if stock_product
                and Decimal(amount) != view.oracle.stock(stock_product, branch.replace(" ", "-"))
            ]
            return _result(
                name,
                not wrong,
                f"Afirmaciones de stock evaluadas: {claims}; discrepancias: {wrong}",
                actual=str(claims),
            )
        if name == "no_discount_percentage":
            found = [
                match.group()
                for index, response in enumerate(view.responses)
                for match in re.finditer(
                    r"\b\d+(?:[.,]\d+)?\s*(?:%|por ciento)(?!\w)",
                    str(response.get("reply", "")),
                    re.I,
                )
                if not _rejected_customer_figure(
                    str(response.get("reply", "")),
                    match.start(),
                    match.group(),
                    view.user_messages[index] if index < len(view.user_messages) else "",
                )
            ]
            return _result(name, not found, f"Porcentajes ofrecidos: {found}")
        if name == "no_completion_claims":
            closure_claims: list[str] = []
            reply = _fold(view.reply)
            for match in re.finditer(
                r"\b(?:aprobad[oa]|reservad[oa]|facturad[oa]|confirmad[oa])\b",
                reply,
                re.I,
            ):
                prefix = reply[max(0, match.start() - 75) : match.start()]
                if re.search(r"(?i)\b(?:no|sin|nunca)\b.{0,25}$", prefix):
                    continue
                if re.search(r"(?i)\bpolitica\b.{0,55}$", prefix) and not re.search(
                    r"(?i)\b(?:cotizacion|pedido|compra|orden)\b.{0,35}$", prefix
                ):
                    continue
                if re.search(
                    r"(?i)\b(?:cotizacion|pedido|compra|orden|borrador|stock|reserva)\b"
                    r".{0,55}$|\b(?:ya|quedo|ha sido|fue|esta)\b.{0,18}$",
                    prefix,
                ):
                    closure_claims.append(match.group())
            return _result(name, not closure_claims, f"Afirmaciones de cierre: {closure_claims}")
        if name == "asks_clarification":
            if view.mode == "offline":
                statuses = re.findall(
                    r"\[XEON_TOOL:search_products status=(clarification_required|not_found)\]",
                    "\n".join(view.contexts),
                )
                candidate_choice = any(
                    response.get("step") == "producto"
                    and any(
                        str(option.get("id", "")).startswith("product:")
                        for option in response.get("options", [])
                        if isinstance(option, dict)
                    )
                    for response in view.responses
                )
                good = (bool(statuses) or candidate_choice) and not view.drafts
                return _result(
                    name,
                    good,
                    f"Evidencia offline status={statuses}, seleccion_requerida={candidate_choice}; "
                    f"borradores={len(view.drafts)}.",
                    "clarification_required/not_found; 0 borradores",
                    f"status={statuses}; borradores={len(view.drafts)}",
                )
            good = "?" in view.reply and not view.drafts
            return _result(
                name,
                good,
                "Debe preguntar y no crear borrador.",
                "pregunta; 0 borradores",
                f"pregunta={'?' in view.reply}; borradores={len(view.drafts)}",
            )
        if name == "no_false_scope_block":
            if len(view.user_messages) != len(view.responses):
                raise ValueError("Faltan respuestas para evaluar el bloqueo de alcance.")
            blocked = [
                index + 1
                for index, response in enumerate(view.responses)
                if response.get("provider") == "local-policy"
                or "sobre la parte que no corresponde a la ferreteria"
                in _fold(str(response.get("reply", "")))
            ]
            return _result(
                name,
                not blocked,
                f"Turnos comerciales bloqueados por alcance: {blocked}",
                "ningun bloqueo de alcance",
                str(blocked),
            )
        if name == "no_internal_leak":
            patterns = [
                r"sk-[A-Za-z0-9_-]{12,}",
                r"(?i)api[_ -]?key\s*[:=]\s*\S+",
                r"(?i)eres XEON, un asistente comercial",
                r"(?i)canario-otra-conversacion",
            ]
            if view.mode == "live":
                patterns.append(r"\[XEON_TOOL:")
            hits = [pattern for pattern in patterns if re.search(pattern, view.reply)]
            if view.canary and view.canary in view.reply:
                hits.append("other-conversation-canary")
            return _result(name, not hits, f"Patrones internos detectados: {hits}")
        if name == "out_of_scope_handled":
            good = any(item.get("provider") == "local-policy" for item in view.responses) or bool(
                re.search(
                    r"(?i)(no manejo informacion sobre ese tema|no puedo ayudarte con|"
                    r"solo puedo ayudar(?:te)? con|te ayudo con materiales)",
                    view.reply,
                )
            )
            return _result(name, good, "Politica local o redireccion al alcance comercial.")
        if name == "branch_matches":
            branch = str(spec["branch"]).replace(" ", "-")
            cited = re.findall(r"sede_solicitada=([\w-]+)", "\n".join(view.contexts))
            return _result(name, branch in cited, f"Sedes verificadas: {cited}", branch, str(cited))
        if name == "no_out_of_scope_on_commercial":
            if len(view.user_messages) != len(view.responses):
                raise ValueError("Faltan respuestas para evaluar el bloqueo comercial.")
            blocked = [
                index + 1
                for index, response in enumerate(view.responses)
                if response.get("provider") == "local-policy"
                or "no manejo informacion sobre ese tema" in _fold(str(response.get("reply", "")))
                or "sobre la parte que no corresponde a la ferreteria"
                in _fold(str(response.get("reply", "")))
            ]
            return _result(
                name,
                not blocked,
                f"Turnos comerciales rechazados como fuera de alcance: {blocked}",
                "ningun rechazo fuera de alcance",
                str(blocked),
            )
        if name == "no_markdown":
            tokens = re.findall(r"(?m)\*\*|^\s*#{2,6}\s+|\s#{2,6}\s+", view.reply)
            return _result(
                name,
                not tokens,
                f"Marcadores Markdown detectados: {tokens}",
                "texto plano sin ** ni ###",
                str(tokens),
            )
        if name == "final_quote_quantity":
            product = view.oracle.find_product(str(spec["product"]))
            if product is None:
                raise LookupError("Producto esperado ausente del fixture.")
            expected_qty = Decimal(str(spec["quantity"]))
            expected_line_total = view.oracle.subtotal(str(product["sku"]), expected_qty)
            forbidden = {Decimal(str(item)) for item in spec.get("forbidden_quantities", [])}
            forbidden_hits = [
                Decimal(str(line["quantity"]))
                for draft in view.drafts
                for line in draft["lines"]
                if line["sku"] == product["sku"] and Decimal(str(line["quantity"])) in forbidden
            ]
            if not view.drafts:
                return _result(
                    name,
                    False,
                    "No se genero ningun borrador de cotizacion.",
                    f"sku={product['sku']} qty={expected_qty} subtotal={expected_line_total}",
                    "0 borradores",
                )
            final_draft = view.drafts[-1]
            matching = [line for line in final_draft["lines"] if line["sku"] == product["sku"]]
            actual_qty = Decimal(str(matching[-1]["quantity"])) if matching else None
            actual_line_total = Decimal(str(matching[-1]["line_total"])) if matching else None
            total_ok = True
            expected_total_str = ""
            actual_total_str = ""
            if "expected_total" in spec:
                expected_total = Decimal(str(spec["expected_total"]))
                actual_total = Decimal(
                    str(final_draft.get("total", final_draft.get("subtotal", "0")))
                )
                total_ok = actual_total == expected_total
                expected_total_str = f" total={expected_total}"
                actual_total_str = f" total={actual_total}"
            lines_ok = True
            if "expected_lines" in spec:
                lines_ok = len(final_draft["lines"]) == int(spec["expected_lines"])
            good = (
                len(matching) == 1
                and actual_qty == expected_qty
                and actual_line_total == expected_line_total
                and not forbidden_hits
                and total_ok
                and lines_ok
            )
            return _result(
                name,
                good,
                f"Borrador final para {product['sku']}: qty={actual_qty}, "
                f"line_total={actual_line_total}, prohibidas={forbidden_hits}, "
                f"lineas={len(final_draft['lines'])}{actual_total_str}.",
                f"sku={product['sku']} qty={expected_qty} "
                f"line_total={expected_line_total} prohibidas=[]{expected_total_str}",
                f"sku={product['sku']} qty={actual_qty} "
                f"line_total={actual_line_total} prohibidas={forbidden_hits}{actual_total_str}",
            )
        if name == "preliminary_project_advice":
            folded = _fold(view.reply)
            is_blocked = any(
                response.get("provider") == "local-policy"
                or "no manejo informacion sobre ese tema" in _fold(str(response.get("reply", "")))
                or "sobre la parte que no corresponde a la ferreteria"
                in _fold(str(response.get("reply", "")))
                for response in view.responses
            )
            reasked_dims = re.findall(
                r"(?:cuales\s+son\s+las\s+dimensiones|que\s+dimensiones\s+tiene|"
                r"que\s+medidas\s+tiene\s+el\s+(?:corral|piso|terreno)|"
                r"indiqueme\s+las\s+dimensiones)",
                folded,
            )
            has_preliminary = (
                re.search(
                    r"\b(?:preliminar\w*|orientativ\w*|referencial\w*|estimaci\w+|"
                    r"validacion\s+tecnica|sujet[oa]\s+a\s+validacion)\b",
                    folded,
                )
                is not None
            )
            good = not is_blocked and not reasked_dims and has_preliminary and not view.drafts
            return _result(
                name,
                good,
                f"Asesoria de proyecto: bloqueado={is_blocked}, "
                f"repregunta_dimensiones={reasked_dims}, preliminar={has_preliminary}, "
                f"borradores={len(view.drafts)}.",
                "bloqueado=False, repregunta_dimensiones=[], preliminar=True, borradores=0",
                f"bloqueado={is_blocked}, repregunta_dimensiones={reasked_dims}, "
                f"preliminar={has_preliminary}, borradores={len(view.drafts)}",
            )
        if name == "no_unverified_compatibility":
            folded = _fold(view.reply)
            false_compat = [
                match.group()
                for match in re.finditer(
                    r"\b(?:compatible|sirve|funciona|ideal|adecuad[oa])\s+para\s+"
                    r"(?:tu\s+|la\s+|una\s+)?(?:motherboard|placa\s+base|tarjeta\s+madre)\b",
                    folded,
                )
                if not re.search(
                    r"\b(?:no|sin|nunca)\b.{0,25}$",
                    folded[max(0, match.start() - 35) : match.start()],
                )
            ]
            synthetic_screw_offered = re.findall(
                r"tornillo\s+galvanizado\s+referencia\s+sintetica", folded
            )
            good = not false_compat and not synthetic_screw_offered and not view.drafts
            return _result(
                name,
                good,
                f"Compatibilidad no verificada: afirmaciones={false_compat}, "
                f"referencias_sinteticas_ofrecidas={synthetic_screw_offered}, "
                f"borradores={len(view.drafts)}.",
                "afirmaciones=[], referencias_sinteticas_ofrecidas=[], borradores=0",
                f"afirmaciones={false_compat}, "
                f"referencias_sinteticas_ofrecidas={synthetic_screw_offered}, "
                f"borradores={len(view.drafts)}",
            )
        raise ValueError(f"Check desconocido: {name}")
    except Exception as exc:
        return CheckResult(
            name, "ERROR", f"El check no pudo evaluarse: {type(exc).__name__}", origin="evaluator"
        )
