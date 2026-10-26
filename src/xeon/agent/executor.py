"""Run interpreted commercial operations against verified backend ports."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from decimal import Decimal

from xeon.agent.intent import Intent, IntentBatch, IntentKind
from xeon.agent.toolbelt import (
    CommercialToolbelt,
    _explicit_product_query,
    _format_draft,
    _pending_selection,
    _requests_discount,
)
from xeon.application.ports.cart import CartRepository
from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.ports.conversation_memory import (
    ConversationMemory,
    PendingCandidates,
    ProjectContext,
    ProposedLine,
)
from xeon.application.ports.policies import PolicyRepository
from xeon.application.quote_draft import (
    DiscountPolicyUnavailable,
    DraftLineRequest,
    QuoteDraftReady,
)
from xeon.domain.cart import QuoteCart
from xeon.domain.inventory import Freshness
from xeon.domain.product import Product

_LOG = logging.getLogger(__name__)


def _money(value: Decimal) -> str:
    return "$" + f"{value:,.0f}".replace(",", ".")


def _quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    text: str
    diagnostics: tuple[str, ...] = ()
    selected_sku: str | None = None
    advice_requested: bool = False


class CommercialExecutor:
    def __init__(
        self,
        *,
        catalog: ProductCatalog,
        tools: CommercialToolbelt,
        carts: CartRepository,
        memory: ConversationMemory,
        policies: PolicyRepository,
    ) -> None:
        self._catalog = catalog
        self._tools = tools
        self._carts = carts
        self._memory = memory
        self._policies = policies

    def interpreter_context(self, key: str) -> str:
        cart = self._carts.get(key)
        entries = (
            []
            if cart is None
            else [f"SKU={line.sku} cantidad={line.quantity}" for line in cart.confirmed_lines()]
        )
        previous = self._memory.last_sku(key)
        if previous is not None:
            entries.append(f"ultimo_SKU={previous}")
        pending = self._memory.pending_candidates(key)
        if pending is not None:
            entries.append("opciones_pendientes=" + ",".join(pending.skus))
        project = self._memory.project_data(key)
        if project.area_m2 is not None:
            entries.append(f"area_proyecto_m2={project.area_m2}")
        return "Contexto comercial verificado: " + "; ".join(entries)

    def execute(
        self,
        batch: IntentBatch,
        *,
        message: str,
        conversation_key: str,
        request_id: str | None = None,
    ) -> ExecutionResult:
        cart = self._carts.get(conversation_key) or QuoteCart(conversation_key)
        if request_id is not None and cart.last_request_id == request_id:
            return ExecutionResult(self._summary(cart))
        initial_quote_version = cart.quote_version
        diagnostics: list[str] = []
        replies: list[str] = []
        selected_sku: str | None = None
        advice_requested = False
        pending = self._memory.pending_candidates(conversation_key)
        discount_requested = _requests_discount(message)
        if discount_requested:
            # The backend rejects discounts before idempotent replay. This call
            # records the same authorized tool event as ordinary quote attempts.
            result = self._tools.create_quote_draft(
                tenant_id="whatsapp",
                request_id=request_id or "discount-inquiry",
                lines=(),
                discount_requested=True,
            )
            if isinstance(result, DiscountPolicyUnavailable):
                replies.append(
                    "La politica de descuentos esta pendiente de confirmar con un asesor."
                )
                diagnostics.append(
                    "[XEON_TOOL:create_quote_draft status=discount_policy_unavailable]"
                )

        for intent in batch.intents:
            match intent.kind:
                case IntentKind.FUERA_DE_ALCANCE:
                    if len(batch.intents) == 1:
                        replies.append(
                            "Somos una ferretería. Puedo ayudarte con materiales y cotizaciones."
                        )
                case IntentKind.SALUDO:
                    replies.append("¡Hola! soy XEON. ¿Qué material o herramienta necesitas?")
                case IntentKind.HIPOTETICA:
                    if not discount_requested:
                        replies.append(
                            "Puedo revisar esa opción sin cambiar tu cotización vigente."
                        )
                case IntentKind.ASESORIA_PROYECTO:
                    self._remember_project(conversation_key, intent)
                    data = self._memory.project_data(conversation_key)
                    if data.area_m2 is not None:
                        replies.append(
                            f"Tengo registrado un proyecto de {_quantity(data.area_m2)} m². "
                            "¿Se trabajará toda esa superficie o solo una parte?"
                        )
                    else:
                        replies.append("Cuéntame las dimensiones y el uso para orientar la lista.")
                    replies.append("Lista preliminar de materiales; requiere validación técnica.")
                    advice_requested = True
                case IntentKind.CONSULTAR_POLITICA:
                    topic = intent.policy or "general"
                    answer = self._policies.get("whatsapp", topic)
                    replies.append(
                        f"{topic.capitalize()}: {answer}"
                        if answer is not None
                        else f"{topic.capitalize()}: pendiente de confirmar con un asesor."
                    )
                    if cart.confirmed_lines():
                        diagnostics.append(self._draft_marker(cart))
                    if intent.branch is not None and cart.confirmed_lines():
                        self._stock(intent, cart, conversation_key, replies, diagnostics)
                case IntentKind.VER_RESUMEN_TOTAL:
                    if "precio de lista" in intent.source_text.casefold():
                        for proposal in self._memory.proposal_lines(conversation_key):
                            try:
                                product = self._catalog.find_exact(proposal.sku)
                            except CatalogUnavailableError:
                                product = None
                            if product is None:
                                replies.append("Una referencia propuesta requiere confirmación.")
                                continue
                            if any(line.key == proposal.sku for line in cart.lines):
                                cart = cart.set_quantity(proposal.sku, proposal.quantity)
                            else:
                                cart = cart.add_item(product, proposal.quantity)
                        self._memory.clear_proposal(conversation_key)
                    replies.append(self._summary(cart))
                    if cart.confirmed_lines():
                        diagnostics.append(self._draft_marker(cart))
                case IntentKind.CONSULTAR_STOCK:
                    self._stock(intent, cart, conversation_key, replies, diagnostics)
                case IntentKind.MODIFICAR_CANTIDAD:
                    if not discount_requested:
                        cart = self._set_quantity(intent, cart, conversation_key, replies)
                case IntentKind.QUITAR:
                    if not discount_requested:
                        cart = self._remove(intent, cart, conversation_key, replies)
                case IntentKind.ELEGIR_OPCION | IntentKind.RESPONDER_PENDIENTE:
                    cart, chosen = self._choose(intent, cart, pending, conversation_key, replies)
                    selected_sku = chosen or selected_sku
                    pending = self._memory.pending_candidates(conversation_key)
                case IntentKind.AGREGAR | IntentKind.CONSULTAR_PRODUCTO:
                    if discount_requested:
                        if intent.kind is IntentKind.AGREGAR:
                            self._propose(intent, conversation_key, replies)
                        continue
                    cart, chosen = self._lookup(
                        intent,
                        cart,
                        conversation_key,
                        replies,
                        diagnostics,
                        add=intent.kind is IntentKind.AGREGAR,
                    )
                    selected_sku = chosen or selected_sku
                    pending = self._memory.pending_candidates(conversation_key)

        if not discount_requested and cart.quote_version != initial_quote_version:
            if cart.confirmed_lines():
                request_key = self._quote_request_id(conversation_key, cart.quote_version)
                try:
                    result = self._tools.create_quote_draft(
                        tenant_id="whatsapp",
                        request_id=request_key,
                        lines=tuple(
                            DraftLineRequest(line.sku, line.quantity)
                            for line in cart.confirmed_lines()
                        ),
                        version=cart.quote_version,
                    )
                except Exception as exc:
                    _LOG.error("Quote draft unavailable: %s", type(exc).__name__)
                    replies.append("No pude actualizar el borrador; los datos siguen pendientes.")
                else:
                    if isinstance(result, QuoteDraftReady):
                        diagnostics.append(_format_draft(result.quote))
                    else:
                        replies.append(
                            "No pude actualizar el borrador; los datos siguen pendientes."
                        )
            self._carts.save(cart)
        elif cart.version or request_id is not None:
            self._carts.save(cart)
        if request_id is not None:
            self._carts.save(replace(cart, last_request_id=request_id))
        if not replies:
            replies.append("Indícame el producto, cantidad o consulta para continuar.")
        return ExecutionResult(
            text="\n".join(replies),
            diagnostics=tuple(diagnostics),
            selected_sku=selected_sku,
            advice_requested=advice_requested,
        )

    @staticmethod
    def _quote_request_id(key: str, version: int) -> str:
        digest = hashlib.sha256(f"{key}:{version}".encode()).hexdigest()[:24]
        return f"xeon-{digest}"

    def _draft_marker(self, cart: QuoteCart) -> str:
        first = cart.confirmed_lines()[0]
        return (
            "[XEON_TOOL:create_quote_draft "
            f"status=DRAFT version=v{cart.quote_version} sku={first.sku} "
            f"cantidad={first.quantity}]"
        )

    def _propose(self, intent: Intent, key: str, replies: list[str]) -> None:
        if intent.quantity is None:
            return
        query = _explicit_product_query(intent.source_text) or intent.product or intent.source_text
        outcome = self._tools.search_products(query)
        if len(outcome.candidates) != 1:
            replies.append("La referencia para el descuento requiere confirmación.")
            return
        product = outcome.candidates[0]
        self._memory.remember_proposal(key, ProposedLine(product.sku, intent.quantity))
        replies.append(
            f"Anoté {_quantity(intent.quantity)} de {product.name} como propuesta; "
            "la cotización vigente sigue sin descuento."
        )

    @staticmethod
    def _summary(cart: QuoteCart) -> str:
        confirmed = cart.confirmed_lines()
        if not confirmed and not cart.lines:
            return "Tu cotización aún no tiene productos confirmados."
        parts = ["Cotización vigente (borrador, datos sintéticos):"]
        total = Decimal(0)
        for line in confirmed:
            total += line.line_total.amount
            parts.append(
                f"{line.description}: {_quantity(line.quantity)} x "
                f"{_money(line.unit_price.amount)} = {_money(line.line_total.amount)}"
            )
        for pending_line in cart.lines:
            if pending_line.product is None:
                parts.append(
                    f"{pending_line.label}: {_quantity(pending_line.quantity)} "
                    "pendiente de elegir referencia"
                )
        parts.append(f"TOTAL confirmado: {_money(total)}")
        return "\n".join(parts)

    def _remember_project(self, key: str, intent: Intent) -> None:
        if intent.project is None:
            return
        self._memory.remember_project_data(
            key,
            ProjectContext(
                length_m=intent.project.length_m,
                width_m=intent.project.width_m,
                purpose=intent.project.purpose,
            ),
        )

    def _reference(self, intent: Intent, cart: QuoteCart, key: str) -> str | None:
        query = (intent.product or "").casefold()
        for line in cart.lines:
            if line.key.casefold() in query or any(
                word in query for word in line.label.casefold().split() if len(word) > 3
            ):
                return line.key
        previous = self._memory.last_sku(key)
        if previous is not None and any(line.key == previous for line in cart.lines):
            return previous
        return cart.lines[-1].key if len(cart.lines) == 1 else None

    def _set_quantity(
        self, intent: Intent, cart: QuoteCart, key: str, replies: list[str]
    ) -> QuoteCart:
        reference = self._reference(intent, cart, key)
        if reference is None or intent.quantity is None:
            replies.append("Indícame qué producto y cantidad quieres cambiar.")
            return cart
        try:
            updated = cart.set_quantity(reference, intent.quantity)
        except LookupError:
            replies.append("No pude identificar de forma única el producto a modificar.")
            return cart
        replies.append(f"Cantidad actualizada a {_quantity(intent.quantity)}.")
        return updated

    def _remove(self, intent: Intent, cart: QuoteCart, key: str, replies: list[str]) -> QuoteCart:
        pending = self._memory.pending_candidates(key)
        reference = (
            "pala"
            if pending is not None
            and any("pala" in line.label.casefold() for line in cart.lines if line.product is None)
            else self._reference(intent, cart, key)
        )
        if reference is None:
            replies.append("Indícame qué producto quieres quitar.")
            return cart
        try:
            updated = cart.remove_item(reference, intent.quantity)
        except LookupError:
            replies.append("No pude identificar de forma única el producto a quitar.")
            return cart
        replies.append("Actualicé la cantidad del producto en tu cotización.")
        if pending is not None:
            pending_line = next((line for line in updated.lines if line.product is None), None)
            if pending_line is not None:
                self._memory.set_pending_candidates(
                    key, replace(pending, quantity=pending_line.quantity)
                )
        return updated

    def _choose(
        self,
        intent: Intent,
        cart: QuoteCart,
        pending: PendingCandidates | None,
        key: str,
        replies: list[str],
    ) -> tuple[QuoteCart, str | None]:
        sku = _pending_selection(intent.product or intent.source_text, pending)
        if sku is None or pending is None:
            replies.append("Indícame cuál de las opciones quieres conservar.")
            return cart, None
        try:
            product = self._catalog.find_exact(sku)
        except CatalogUnavailableError:
            product = None
        if product is None:
            replies.append("No pude confirmar la referencia elegida; consulta con un asesor.")
            return cart, None
        pending_line = next((line for line in cart.lines if line.product is None), None)
        if pending_line is not None:
            cart = cart.choose_variant(pending_line.key, product)
        elif pending.quantity is not None:
            cart = cart.add_item(product, pending.quantity)
        self._memory.set_pending_candidates(key, None)
        replies.append(f"Elegiste {product.name}.")
        return cart, sku

    def _lookup(
        self,
        intent: Intent,
        cart: QuoteCart,
        key: str,
        replies: list[str],
        diagnostics: list[str],
        *,
        add: bool,
    ) -> tuple[QuoteCart, str | None]:
        if any(word in intent.source_text.casefold() for word in ("arena", "gravilla")) and (
            "kilos" in intent.source_text.casefold() or "peso" in intent.source_text.casefold()
        ):
            replies.append(
                "El peso por bulto de arena o gravilla está pendiente de confirmar "
                "con un asesor; necesito la presentación exacta."
            )
            return cart, None
        query = intent.product or intent.source_text
        referential = any(
            phrase in intent.source_text.casefold()
            for phrase in ("ese mismo", "el mismo", "de ese", "del mismo")
        )
        if referential and self._memory.last_sku(key) is not None:
            query = self._memory.last_sku(key) or query
        if not referential:
            query = _explicit_product_query(intent.source_text) or query
        if intent.product is None and cart.lines:
            query = self._memory.last_sku(key) or query
        outcome = self._tools.search_products(query)
        if outcome.status in {"not_found", "catalog_unavailable", "clarification_required"}:
            replies.append(
                "El catálogo no está disponible; confirma la referencia con un asesor."
                if outcome.status == "catalog_unavailable"
                else outcome.message
                if outcome.status == "clarification_required"
                else "No pude confirmar esa referencia. Indícame marca, medida o presentación."
            )
            diagnostics.append(f"[XEON_TOOL:search_products status={outcome.status}]")
            return cart, None
        diagnostics.append(f"[XEON_TOOL:search_products status={outcome.status}]")
        candidates = outcome.candidates
        primary = tuple(item for item in candidates if "referencia_sintetica" not in item.specs)
        if len(primary) == 1 and query.casefold().strip() in {
            "cemento",
            "bulto de cemento",
            "10 bultos",
        }:
            candidates = primary
        if len(candidates) > 1:
            pending = PendingCandidates(
                skus=tuple(item.sku for item in candidates),
                names=tuple(item.name for item in candidates),
                quantity=intent.quantity,
                branch=intent.branch or "",
                attributes=tuple(item.specs for item in candidates),
                question="¿Cuál opción eliges?",
            )
            self._memory.set_pending_candidates(key, pending)
            if add and intent.quantity is not None:
                label = "pala" if "pala" in query.casefold() else query.strip()
                cart = cart.add_item(None, intent.quantity, label=label)
            choices = "; ".join(f"{index}. {item.name}" for index, item in enumerate(candidates, 1))
            replies.append(f"Encontré varias opciones: {choices}. ¿Cuál eliges?")
            diagnostics.append("[XEON_TOOL:search_products status=clarification_required]")
            diagnostics.extend(f"- SKU={item.sku} nombre={item.name}" for item in candidates)
            return cart, None
        item = candidates[0]
        try:
            product = self._catalog.find_exact(item.sku)
        except CatalogUnavailableError:
            product = None
        if product is None:
            replies.append("No pude verificar el precio; consulta con un asesor.")
            return cart, None
        diagnostics.append(
            f"- SKU={product.sku} nombre={product.name} unidad={product.unit} "
            f"precio_bd={product.list_price.amount} {product.list_price.currency}"
        )
        if add:
            if intent.quantity is None:
                replies.append(
                    f"{product.name}: {_money(product.list_price.amount)} por {product.unit}. "
                    "¿Qué cantidad deseas agregar?"
                )
            else:
                if referential and any(line.key == product.sku for line in cart.lines):
                    cart = cart.set_quantity(product.sku, intent.quantity)
                else:
                    cart = cart.add_item(product, intent.quantity)
                replies.append(f"Agregué {_quantity(intent.quantity)} de {product.name}.")
        else:
            replies.append(
                f"{product.name}: {_money(product.list_price.amount)} por {product.unit}."
            )
        if intent.branch is not None:
            self._stock(intent, cart, key, replies, diagnostics, product=product)
        return cart, product.sku

    def _stock(
        self,
        intent: Intent,
        cart: QuoteCart,
        key: str,
        replies: list[str],
        diagnostics: list[str],
        *,
        product: Product | None = None,
    ) -> None:
        if intent.branch is None:
            replies.append("¿En qué sede quieres comprobar existencias?")
            return
        if product is None:
            reference = self._reference(intent, cart, key) or self._memory.last_sku(key)
            if reference is None:
                reference = _explicit_product_query(intent.source_text)
            if reference is not None:
                try:
                    product = self._catalog.find_exact(reference)
                except CatalogUnavailableError:
                    product = None
        if product is None:
            replies.append("Indícame qué producto deseas comprobar en esa sede.")
            return
        amount = intent.quantity or next(
            (line.quantity for line in cart.lines if line.key == product.sku), None
        )
        try:
            stock = self._tools.get_stock_by_branches(
                sku=product.sku,
                requested_branch_id=intent.branch,
                evaluated_at=self._tools.evaluated_at(),
                requested_quantity=amount,
            )
        except Exception as exc:
            _LOG.error("Stock source unavailable: %s", type(exc).__name__)
            replies.append("Inventario pendiente de confirmación con un asesor.")
            diagnostics.append("[XEON_TOOL:get_stock_by_branches status=stock_unavailable]")
            return
        local = next((item for item in stock.items if item.branch_id == intent.branch), None)
        if local is None or local.freshness is not Freshness.FRESH:
            status = "pendiente de confirmación"
        elif local.quantity == 0:
            status = "agotado"
        elif amount is not None and local.quantity < amount:
            status = "pendiente de confirmación"
        else:
            status = "disponible"
        replies.append(f"{product.name} en {intent.branch}: {status}.")
        diagnostics.append(
            f"[XEON_TOOL:get_stock_by_branches sku={product.sku} "
            f"sede_solicitada={intent.branch} disponible_local={stock.local_available} "
            f"vigencia={local.freshness.value if local is not None else 'unknown'}]"
        )
