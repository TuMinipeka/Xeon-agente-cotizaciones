"""Guided quotation state machine; commercial mutations go through CommercialExecutor."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from xeon.agent.executor import CommercialExecutor
from xeon.agent.intent import (
    Intent,
    IntentBatch,
    IntentKind,
    fallback_intents,
    is_explicit_addition,
)
from xeon.agent.toolbelt import CommercialToolbelt, _explicit_product_query
from xeon.application.ports.advisor import AdvisorNotifier
from xeon.application.ports.branches import BranchDirectory
from xeon.application.ports.cart import CartRepository
from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.ports.conversation_memory import ConversationMemory
from xeon.application.ports.funnel import FunnelRepository, FunnelState
from xeon.application.ports.llm import ChatMessage, LLMPort, LLMProviderError
from xeon.application.ports.policies import PolicyRepository
from xeon.application.ports.quotes import QuoteDraftRepository
from xeon.application.reply import Option, Reply
from xeon.domain.quote import QuoteStatus


def _normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


class StepChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: str


class GuidedFunnel:
    def __init__(
        self,
        *,
        llm: LLMPort,
        executor: CommercialExecutor,
        tools: CommercialToolbelt,
        catalog: ProductCatalog,
        carts: CartRepository,
        quotes: QuoteDraftRepository,
        states: FunnelRepository,
        branches: BranchDirectory,
        policies: PolicyRepository,
        notifier: AdvisorNotifier,
        memory: ConversationMemory,
        tenant_id: str,
    ) -> None:
        self._llm = llm
        self._executor = executor
        self._tools = tools
        self._catalog = catalog
        self._carts = carts
        self._quotes = quotes
        self._states = states
        self._branches = branches
        self._policies = policies
        self._notifier = notifier
        self._memory = memory
        self._tenant_id = tenant_id

    def state(self, key: str) -> FunnelState:
        return self._states.get(key)

    def _save(self, key: str, state: FunnelState) -> FunnelState:
        self._states.save(key, state)
        return state

    def _cart(self, key: str) -> str:
        return self._executor.execute(
            IntentBatch(intents=(Intent(kind=IntentKind.VER_RESUMEN_TOTAL),)),
            message="ver cotizacion",
            conversation_key=key,
        ).text

    def _options(self, key: str, state: FunnelState) -> tuple[Option, ...]:
        policy = self._policies.load(self._tenant_id)
        options: tuple[Option, ...]
        match state.step:
            case "inicio":
                options = (
                    Option("start:products", "Cotizar productos"),
                    Option("start:project", "Proyecto u obra"),
                    Option("global:advisor", "Hablar con asesor"),
                )
            case "producto" if state.candidates:
                options = tuple(
                    Option(f"product:{sku}", self._product_title(sku))
                    for sku in state.candidates[:8]
                )
            case "cantidad":
                unit = self._selected_unit(state.selected_sku)
                suggested = (10, 50) if unit == "metro" else (10, 20) if unit == "bulto" else (1, 2)
                options = (
                    Option(f"quantity:{suggested[0]}", str(suggested[0])),
                    Option(f"quantity:{suggested[1]}", str(suggested[1])),
                    Option("quantity:other", "Otra"),
                )
            case "mas":
                options = (
                    Option("more:add", "Agregar otro"),
                    Option("more:view", "Ver cotizacion"),
                    Option("more:modify", "Modificar"),
                )
            case "modificar" if state.selected_line is None:
                cart = self._carts.get(key)
                options = tuple(
                    Option(f"line:{index}", line.label[:24])
                    for index, line in enumerate(cart.lines[:8] if cart else ())
                )
            case "modificar":
                options = (
                    Option("modify:quantity", "Cambiar cantidad"),
                    Option("modify:remove", "Quitar"),
                )
            case "entrega":
                delivery = policy.entrega
                options = ()
                if delivery and delivery.recoger_en_sede and delivery.recoger_en_sede.disponible:
                    options += (Option("delivery:pickup", "Recoger en sede"),)
                if delivery and delivery.domicilio and delivery.domicilio.disponible:
                    options += (Option("delivery:home", "Domicilio"),)
                if not options:
                    options = (Option("delivery:branch_inquiry", "Consultar sede"),)
                options += (Option("global:advisor", "Hablar con asesor"),)
                if len(options) < 3:
                    options += (Option("global:cancel", "Cancelar"),)
            case "sede":
                options = tuple(
                    Option(
                        f"branch:{branch.id}",
                        self._branch_title(key, branch.id, branch.name),
                    )
                    for branch in self._branches.list_branches()[:8]
                )
            case "pago":
                options = (
                    tuple(
                        Option(f"payment:{index}", method[:24])
                        for index, method in enumerate(policy.pagos[:8])
                    )
                    if policy.pagos
                    else (Option("payment:pending", "Pendiente asesor"),)
                )
            case "resumen":
                options = (
                    Option("summary:confirm", "Confirmar"),
                    Option("summary:modify", "Modificar"),
                    Option("global:cancel", "Cancelar"),
                )
            case "proyecto":
                options = (
                    Option("project:home", "Vivienda"),
                    Option("project:renovation", "Remodelacion"),
                    Option("project:other", "Otra obra"),
                )
            case _:
                options = ()
        return options[:10]

    def _selected_unit(self, sku: str | None) -> str:
        if sku is None:
            return "unidad"
        try:
            product = self._catalog.find_exact(sku)
        except CatalogUnavailableError:
            product = None
        unit = _normalized(product.unit).strip() if product else ""
        if unit.startswith(("bulto", "saco")):
            return "bulto"
        if unit.startswith("metro") or unit == "m":
            return "metro"
        return "unidad"

    def _product_title(self, sku: str) -> str:
        return self._product_name(sku)[:24]

    def _product_name(self, sku: str) -> str:
        try:
            product = self._catalog.find_exact(sku)
        except CatalogUnavailableError:
            product = None
        return product.name if product else sku

    def _branch_title(self, key: str, branch_id: str, name: str) -> str:
        status = self._branch_stock(key, branch_id)
        available = 24 - len(status) - 2
        label = name if len(name) <= available else name.split()[-1][:available]
        return f"{label}: {status}"

    def _branch_stock(self, key: str, branch_id: str) -> str:
        cart = self._carts.get(key)
        if cart is None or not cart.confirmed_lines():
            return "pendiente"
        line = cart.confirmed_lines()[0]
        result = self._executor.execute(
            IntentBatch(
                intents=(
                    Intent(
                        kind=IntentKind.CONSULTAR_STOCK,
                        product=line.sku,
                        quantity=line.quantity,
                        branch=branch_id,
                        source_text=line.sku,
                    ),
                )
            ),
            message=line.sku,
            conversation_key=key,
        )
        for status in ("disponible", "agotado", "pendiente"):
            if status in _normalized(result.text):
                return status
        return "pendiente"

    def render(self, key: str, *, prefix: str = "") -> Reply:
        state = self.state(key)
        project = self._memory.project_data(key)
        project_text = ""
        if project.area_m2 is not None:
            project_text = f"Proyecto de {project.area_m2:,.0f} m² registrado. "
            if project.whole_surface is True:
                project_text += "Toda la superficie confirmada. "
            elif project.whole_surface is None:
                project_text += "¿Se trabajará toda la superficie o solo una parte? "
        questions = {
            "inicio": "¿Qué necesitas?",
            "producto": "¿Qué producto buscas? Escribe nombre o referencia.",
            "cantidad": f"¿Cuántas unidades de {self._product_name(state.selected_sku or '')}?",
            "mas": "¿Algo más para tu cotización?",
            "modificar": "¿Qué línea cambias?"
            if state.selected_line is None
            else "¿Qué cambio hacemos?",
            "entrega": "¿Cómo lo recibes?",
            "sede": "¿En qué sede lo recoges? Stock sujeto a confirmación.",
            "direccion": (
                "Escribe tu barrio o dirección. El costo de domicilio lo confirma un asesor."
            ),
            "pago": "¿Cómo prefieres pagar?",
            "resumen": self._cart(key) + self._summary_details(state),
            "proyecto": project_text
            + ("¿Qué vas a construir? La lista será preliminar y requiere validación técnica."),
            "asesor": "Un asesor te contactará.",
            "confirmado": "Recibimos tu confirmación. Un asesor revisará y te contactará.",
            "cancelado": "Cotización cancelada.",
        }
        options = self._options(key, state)
        kind: Literal["text", "buttons", "list"] = (
            "text"
            if not options
            else "buttons"
            if state.step not in {"producto", "sede", "pago", "modificar"}
            and len(options) <= 3
            and all(len(item.title) <= 20 for item in options)
            else "list"
        )
        return Reply(
            text=(prefix + questions[state.step]).strip(),
            kind=kind,
            options=options,
            step=state.step,
        )

    def _summary_details(self, state: FunnelState) -> str:
        policy = self._policies.load(self._tenant_id)
        unknown = "pendiente de confirmar con un asesor"
        delivery = state.delivery or unknown
        location = state.branch_id or state.address or unknown
        validity = (
            str(policy.vigencia_cotizacion_dias) + " días"
            if policy.vigencia_cotizacion_dias
            else unknown
        )
        return (
            f"\nEntrega: {delivery} ({location}). Pago: {state.payment or unknown}. "
            f"Vigencia: {validity}. IVA: {policy.iva or unknown}."
        )

    @staticmethod
    def _is_weight_question(message: str) -> bool:
        return bool(re.search(r"\b(?:kilos?|peso|kg)\b", message)) and bool(
            re.search(r"\b(?:bultos?|cemento|arena|gravilla)\b", message)
        )

    @staticmethod
    def _is_project_statement(message: str) -> bool:
        return bool(re.search(r"\b(?:corral|proyecto|superficie|piso de concreto)\b", message))

    def _answer_weight_and_delivery(self, key: str, message: str) -> str:
        cart = self._carts.get(key)
        products = [line.product for line in cart.lines if line.product is not None] if cart else []
        if "cemento" in _normalized(message):
            products = [product for product in products if "cemento" in _normalized(product.name)]
        product = products[0] if len(products) == 1 else None
        if product is None:
            weight = "El peso del bulto está pendiente de confirmar con un asesor."
        else:
            declared = product.specs_dict.get("peso_kg")
            match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*kg\b", product.name, re.I)
            kilos = declared or (match.group(1) if match else None)
            weight = (
                f"El bulto de {product.name} trae {kilos} kg según el catálogo."
                if kilos
                else f"El peso de {product.name} está pendiente de confirmar con un asesor."
            )
        if "domicilio" in _normalized(message):
            weight += " " + self._policy_answer("domicilio")
        return weight

    @staticmethod
    def _policy_topics(message: str) -> tuple[str, ...]:
        rules = (
            ("horario", r"\b(?:horarios?|abren|cierran|atienden|domingo|sabado)\b"),
            ("domicilio", r"\b(?:domicilio|envio|entrega a domicilio)\b"),
            ("recogida", r"\b(?:recoger|recogida|retiro en sede)\b"),
            ("pago", r"\b(?:pagos?|pagar|efectivo|transferencia|tarjeta|nequi)\b"),
            ("iva", r"\b(?:iva|impuestos?)\b"),
            ("descuento", r"\b(?:descuentos?|rebajas?)\b"),
            ("vigencia", r"\b(?:vigencia|vence|vencimiento|validez|valida)\b"),
        )
        normalized = _normalized(message)
        return tuple(topic for topic, pattern in rules if re.search(pattern, normalized))

    def _policy_answer(self, topic: str) -> str:
        policy = self._policies.load(self._tenant_id)
        pending = "pendiente de confirmar con un asesor"
        if topic == "horario":
            hours = policy.horario
            details = (
                (
                    ("lunes a viernes", hours.lunes_a_viernes),
                    ("sábado", hours.sabado),
                    ("domingo", hours.domingo),
                )
                if hours
                else (("lunes a viernes", None), ("sábado", None), ("domingo", None))
            )
            return (
                "Horario: "
                + "; ".join(f"{day}: {value or pending}" for day, value in details)
                + "."
            )
        if topic in {"domicilio", "recogida"}:
            delivery = policy.entrega
            option = (
                (delivery.domicilio if topic == "domicilio" else delivery.recoger_en_sede)
                if delivery
                else None
            )
            title = "Domicilio" if topic == "domicilio" else "Recogida en sede"
            if option is None or option.disponible is None:
                return f"{title}: {pending}."
            if not option.disponible:
                return f"{title}: no disponible."
            detail = option.costo if topic == "domicilio" else option.nota
            return f"{title}: disponible; {detail or pending}."
        if topic == "pago":
            return "Medios de pago: " + (", ".join(policy.pagos) if policy.pagos else pending) + "."
        if topic == "iva":
            return f"IVA: {policy.iva or pending}."
        if topic == "descuento":
            return f"Politica de descuentos: {policy.descuentos or pending}."
        return "Vigencia: " + (
            f"{policy.vigencia_cotizacion_dias} días."
            if policy.vigencia_cotizacion_dias is not None
            else f"{pending}."
        )

    async def handle(
        self, key: str, message: str, *, option_id: str | None = None, request_id: str | None = None
    ) -> Reply:
        async with self._states.conversation(key):
            return await self._handle_locked(
                key, message, option_id=option_id, request_id=request_id
            )

    async def _handle_locked(
        self, key: str, message: str, *, option_id: str | None = None, request_id: str | None = None
    ) -> Reply:
        state = self.state(key)
        if request_id is not None and state.last_request_id == request_id and state.last_reply:
            return state.last_reply
        reply = await self._handle_step(key, message, option_id=option_id, request_id=request_id)
        if request_id is not None:
            self._save(
                key,
                replace(self.state(key), last_request_id=request_id, last_reply=reply),
            )
        return reply

    async def _handle_step(
        self, key: str, message: str, *, option_id: str | None = None, request_id: str | None = None
    ) -> Reply:
        state = self.state(key)
        raw = (option_id or message).strip()
        if not raw:
            return self.render(key)
        options = self._options(key, state)
        if option_id is None and raw.isdigit() and not state.awaiting_number:
            index = int(raw) - 1
            if 0 <= index < len(options):
                raw = options[index].id
        if option_id is None and raw in {item.id for item in options}:
            option_id = raw
        if option_id is None:
            matching = [item for item in options if _normalized(raw) == _normalized(item.title)]
            if len(matching) == 1:
                option_id = matching[0].id
        if _normalized(raw) in {"cancelar", "cancela"} or raw == "global:cancel":
            self._save(key, replace(state, step="cancelado"))
            return self.render(key)
        if _normalized(raw) in {"asesor", "hablar con asesor"} or raw == "global:advisor":
            self._notifier.notify(
                tenant_id=self._tenant_id, event="advisor_requested", conversation_key=key
            )
            self._save(key, replace(state, step="asesor"))
            return self.render(key)
        if option_id is not None:
            if option_id not in {item.id for item in options}:
                return self.render(key, prefix="Solo puedo ayudarte con tu cotización.\n")
            raw = option_id
        if state.step in {"confirmado", "cancelado", "asesor"}:
            return self.render(key)
        normalized_message = _normalized(message)
        if (
            option_id is None
            and state.step == "inicio"
            and normalized_message.strip(" !.")
            in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches"}
        ):
            return self.render(key)
        if option_id is None and re.search(
            r"\b(?:motherboard|placa base|tarjeta madre|tornillos? m3|tornillos? 6-32)\b",
            normalized_message,
        ):
            self._memory.set_unverified_pc_context(key, True)
            return self.render(
                key,
                prefix="No tengo compatibilidad verificada para placa base o PC. "
                "Habla con un asesor antes de elegir tornillos.\n",
            )
        if (
            option_id is None
            and self._memory.unverified_pc_context(key)
            and re.search(r"\b(?:tornillos?|m3|6-32|rosca)\b", normalized_message)
        ):
            return self.render(key, prefix="La compatibilidad para PC sigue sin verificar.\n")
        if option_id is None and re.search(r"\b(?:gracias|muchas gracias)\b", normalized_message):
            self._save(key, replace(state, closed=True))
            summary = self._cart(key) if self._carts.get(key) else ""
            return self.render(key, prefix=f"Con gusto. Tu borrador sigue disponible.\n{summary}\n")
        if option_id is None and self._is_weight_question(normalized_message):
            return self.render(key, prefix=self._answer_weight_and_delivery(key, message) + "\n")
        if option_id is None and (topics := self._policy_topics(message)):
            return self.render(
                key, prefix=" ".join(self._policy_answer(topic) for topic in topics) + "\n"
            )
        if option_id is None and self._is_project_statement(normalized_message):
            project_intents = tuple(
                intent
                for intent in fallback_intents(message).intents
                if intent.kind is IntentKind.ASESORIA_PROYECTO
            )
            if project_intents:
                self._executor.execute(
                    IntentBatch(intents=project_intents),
                    message=message,
                    conversation_key=key,
                    request_id=request_id,
                )
                self._save(key, replace(state, step="proyecto"))
                return self.render(key)
        if option_id is None and all(
            intent.kind is IntentKind.FUERA_DE_ALCANCE
            for intent in fallback_intents(message).intents
        ):
            return self.render(key, prefix="Solo puedo ayudarte con tu cotización.\n")
        if option_id is None:
            local = fallback_intents(message)
            operations = [
                intent
                for intent in local.intents
                if intent.kind in {IntentKind.QUITAR, IntentKind.MODIFICAR_CANTIDAD}
            ]
            cart = self._carts.get(key)
            if cart is not None and cart.confirmed_lines():
                for intent in local.intents:
                    if intent.kind is not IntentKind.AGREGAR or intent.quantity is None:
                        continue
                    query = (
                        _explicit_product_query(intent.source_text)
                        or intent.product
                        or intent.source_text
                    )
                    found = self._tools.search_products(query)
                    if len(found.candidates) != 1 or not any(
                        line.sku == found.candidates[0].sku for line in cart.confirmed_lines()
                    ):
                        continue
                    if is_explicit_addition(message):
                        operations.append(intent)
                    else:
                        operations.append(
                            intent.model_copy(update={"kind": IntentKind.MODIFICAR_CANTIDAD})
                        )
            if operations:
                result = self._executor.execute(
                    IntentBatch(intents=tuple(operations)),
                    message=message,
                    conversation_key=key,
                    request_id=request_id,
                )
                self._save(key, replace(state, step="mas"))
                return self.render(key, prefix=result.text + "\n" + self._cart(key) + "\n")
        if state.step == "producto" and option_id is None:
            search_result = self._tools.search_products(message, limit=8)
            if not search_result.candidates:
                return self.render(
                    key, prefix="No encontré una referencia verificada. Indica marca o medida.\n"
                )
            state = self._save(
                key, replace(state, candidates=tuple(item.sku for item in search_result.candidates))
            )
            return self.render(key, prefix="Elige una referencia:\n")
        if state.step == "direccion" and option_id is None:
            self._save(key, replace(state, step="pago", address=message[:200]))
            return self.render(key)
        if state.step == "cantidad" and (
            state.awaiting_number or (option_id is None and re.fullmatch(r"\d+(?:[.,]\d+)?", raw))
        ):
            try:
                amount = Decimal(raw.replace(",", "."))
            except InvalidOperation:
                amount = Decimal(0)
            if amount > 0:
                return self._add_selected(key, state, amount, request_id)
        if option_id is None:
            raw = await self._classify(message, options, state.step)
            if raw == "no_encaja":
                return self.render(key, prefix="Solo puedo ayudarte con tu cotización.\n")
        match state.step, raw:
            case "inicio", "start:products":
                state = replace(state, step="producto")
            case "inicio", "start:project":
                state = replace(state, step="proyecto")
            case "producto", choice if choice.startswith("product:"):
                state = replace(
                    state,
                    step="cantidad",
                    selected_sku=choice.removeprefix("product:"),
                    candidates=(),
                )
            case "cantidad", choice if (
                choice.startswith("quantity:") and choice != "quantity:other"
            ):
                return self._add_selected(
                    key, state, Decimal(choice.removeprefix("quantity:")), request_id
                )
            case "cantidad", "quantity:other":
                state = replace(state, awaiting_number=True)
            case "mas", "more:add":
                state = replace(state, step="producto", selected_sku=None)
            case "mas", "more:view":
                state = replace(state, step="entrega")
            case "mas", "more:modify" | "resumen", "summary:modify":
                state = replace(state, step="modificar", selected_line=None)
            case "modificar", choice if choice.startswith("line:"):
                cart = self._carts.get(key)
                index = int(choice.removeprefix("line:"))
                if cart is None or index >= len(cart.lines):
                    return self.render(key)
                state = replace(state, selected_line=cart.lines[index].key)
            case "modificar", "modify:remove":
                self._execute(key, IntentKind.QUITAR, state.selected_line, None, request_id)
                state = replace(state, step="mas", selected_line=None)
            case "modificar", "modify:quantity":
                state = replace(
                    state,
                    step="cantidad",
                    selected_sku=state.selected_line,
                    awaiting_modification=True,
                )
            case "entrega", "delivery:pickup":
                state = replace(state, step="sede", delivery="recogida")
            case "entrega", "delivery:branch_inquiry":
                state = replace(state, step="sede", delivery=None)
            case "entrega", "delivery:home":
                state = replace(state, step="direccion", delivery="domicilio")
            case "sede", choice if choice.startswith("branch:"):
                branch_id = choice.removeprefix("branch:")
                status = self._branch_stock(key, branch_id)
                branch = next(
                    item for item in self._branches.list_branches() if item.id == branch_id
                )
                state = replace(state, step="pago", branch_id=branch_id)
                self._save(key, state)
                if status == "pendiente":
                    return self.render(
                        key, prefix="Stock pendiente de confirmación con un asesor.\n"
                    )
                return self.render(key, prefix=f"{branch.name}: stock {status}.\n")
            case "pago", choice if choice.startswith("payment:"):
                methods = self._policies.load(self._tenant_id).pagos or []
                if choice == "payment:pending":
                    state = replace(state, step="resumen", payment=None)
                else:
                    index = int(choice.removeprefix("payment:"))
                    if index >= len(methods):
                        return self.render(key)
                    state = replace(state, step="resumen", payment=methods[index])
            case "resumen", "summary:confirm":
                cart = self._carts.get(key)
                if cart is None or not cart.confirmed_lines():
                    return self.render(key, prefix="Agrega al menos un producto confirmado.\n")
                quote_request_id = self._executor.current_quote_request_id(key)
                quote = (
                    self._quotes.get_by_idempotency_key(self._tenant_id, quote_request_id)
                    if quote_request_id is not None
                    else None
                )
                if quote is None:
                    return self.render(
                        key, prefix="Borrador pendiente de confirmar con un asesor.\n"
                    )
                confirmed = self._quotes.save(
                    replace(quote, status=QuoteStatus.CONFIRMADO_POR_CLIENTE)
                )
                self._notifier.notify(
                    tenant_id=self._tenant_id,
                    event="client_confirmed",
                    conversation_key=key,
                    quote_id=confirmed.id,
                )
                state = replace(state, step="confirmado")
            case "proyecto", choice if choice.startswith("project:"):
                lookup = {
                    "project:home": "cemento",
                    "project:renovation": "pintura",
                    "project:other": "pala",
                }
                suggestion = self._tools.search_products(lookup[choice], limit=8)
                state = replace(
                    state,
                    step="producto",
                    candidates=tuple(item.sku for item in suggestion.candidates),
                )
                self._save(key, state)
                return self.render(
                    key,
                    prefix=(
                        "Lista preliminar; requiere validación técnica. "
                        "Elige un producto o busca otro.\n"
                    ),
                )
            case _:
                return self.render(key, prefix="Solo puedo ayudarte con tu cotización.\n")
        self._save(key, state)
        return self.render(key)

    def _execute(
        self,
        key: str,
        kind: IntentKind,
        product: str | None,
        quantity: Decimal | None,
        request_id: str | None,
    ) -> str:
        result = self._executor.execute(
            IntentBatch(
                intents=(
                    Intent(
                        kind=kind, product=product, quantity=quantity, source_text=product or ""
                    ),
                )
            ),
            message=product or "",
            conversation_key=key,
            request_id=request_id,
        )
        return result.text

    def _add_selected(
        self, key: str, state: FunnelState, amount: Decimal, request_id: str | None
    ) -> Reply:
        if state.selected_sku is None:
            return self.render(key)
        kind = IntentKind.MODIFICAR_CANTIDAD if state.awaiting_modification else IntentKind.AGREGAR
        result = self._execute(key, kind, state.selected_sku, amount, request_id)
        self._save(
            key,
            replace(
                state,
                step="mas",
                selected_sku=None,
                awaiting_number=False,
                awaiting_modification=False,
            ),
        )
        summary = self._cart(key) if self._carts.get(key) else ""
        return self.render(key, prefix=result + "\n" + summary + "\n")

    async def _classify(self, message: str, options: tuple[Option, ...], step: str) -> str:
        normalized = _normalized(message)
        for option in options:
            if normalized in {_normalized(option.title), _normalized(option.id)}:
                return option.id
        if self._llm.provider_name == "mock":
            return "no_encaja"
        allowed = [option.id for option in options]
        prompt = (
            "Clasifica el texto en UNA opcion permitida para el paso " + step + ". "
            'Devuelve solo JSON con {"choice":"id"}. '
            "Opciones exactas: " + json.dumps([*allowed, "no_encaja"], ensure_ascii=False) + ". "
            "No redactes una respuesta ni calcules precios."
        )
        try:
            response = await self._llm.complete(
                (
                    ChatMessage(role="system", content=prompt),
                    ChatMessage(role="user", content=message),
                )
            )
            choice = StepChoice.model_validate_json(response.text).choice
        except LLMProviderError, ValidationError:
            return "no_encaja"
        return choice if choice in allowed else "no_encaja"
