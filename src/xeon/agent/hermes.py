from __future__ import annotations

import re
import unicodedata
import uuid
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.quote_draft import (
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    CreateQuoteResult,
    DraftLineRequest,
    QuoteDraftReady,
)
from xeon.application.quote_request import classify_line_query
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery, StockByBranches
from xeon.domain.product import Product


@dataclass(frozen=True, slots=True)
class CandidateProductInfo:
    sku: str
    name: str
    unit: str
    unit_price: str
    currency: str
    specs: dict[str, str]
    source: str
    catalog_version: str


@dataclass(frozen=True, slots=True)
class SearchProductsOutcome:
    status: str
    query: str
    candidates: tuple[CandidateProductInfo, ...] = ()
    clarification_reason: str | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class PendingProductSelection:
    query: str
    candidates: tuple[CandidateProductInfo, ...]
    requested_quantity: Decimal | None
    requested_branch_id: str


@dataclass(frozen=True, slots=True)
class PreparedCustomerTurn:
    verified_context: str | None
    customer_reply: str


@dataclass(frozen=True, slots=True)
class ConversationCartLine:
    product: CandidateProductInfo
    quantity: Decimal


@dataclass(slots=True)
class ConversationState:
    location_name: str | None = None
    branch_id: str | None = None
    deferred_location_query: str | None = None
    pending_selection: PendingProductSelection | None = None
    pending_quantity: CandidateProductInfo | None = None
    cart: dict[str, ConversationCartLine] = field(default_factory=dict)
    deferred_reopen_query: str | None = None
    awaiting_reopen_choice: bool = False
    finalized_draft: bool = False
    recommendations_declined: bool = False
    last_activity: datetime | None = None


_MAX_CONVERSATIONS = 1024
_ASK_TO_RESUME_AFTER = timedelta(hours=24)
_START_NEW_AFTER = timedelta(days=3)
_KNOWN_BRANCHES = {
    "norte": "sede-norte",
    "sur": "sede-sur",
    "centro": "sede-centro",
}


class HermesToolbelt:
    """Bounded commercial orchestration with verified data and in-memory sessions."""

    def __init__(
        self,
        *,
        catalog: ProductCatalog,
        create_quote_draft: CreateQuoteDraft,
        get_stock_by_branches: GetStockByBranches,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._create_quote_draft = create_quote_draft
        self._get_stock_by_branches = get_stock_by_branches
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sessions: OrderedDict[str, ConversationState] = OrderedDict()

    def search_products(self, query: str, *, limit: int = 3) -> SearchProductsOutcome:
        cleaned = query.strip()
        if not cleaned:
            return SearchProductsOutcome(
                status="clarification_required",
                query=query,
                clarification_reason="empty_query",
                message="Se requiere una descripcion para buscar en el catalogo.",
            )
        classified = classify_line_query(cleaned)
        if classified.reason == "missing_units":
            return SearchProductsOutcome(
                status="clarification_required",
                query=cleaned,
                clarification_reason="missing_units",
                message="Faltan unidades; esas medidas no determinan una referencia.",
            )
        try:
            exact = self._catalog.find_exact(cleaned)
            if exact is not None:
                return SearchProductsOutcome(
                    status="exact_match",
                    query=cleaned,
                    candidates=(_candidate_from_product(exact),),
                    message=f"Coincidencia exacta interna para {exact.sku}.",
                )
            if classified.reason == "ambiguous_reference" and _looks_vague(cleaned):
                return SearchProductsOutcome(
                    status="clarification_required",
                    query=cleaned,
                    clarification_reason="ambiguous_reference",
                    message="La referencia necesita una caracteristica observable.",
                )
            candidates = self._catalog.search_candidates(cleaned, limit=limit)
        except CatalogUnavailableError:
            return SearchProductsOutcome(
                status="catalog_unavailable",
                query=cleaned,
                message="El catalogo no esta disponible; desconocido no significa agotado.",
            )
        if not candidates:
            return SearchProductsOutcome(
                status="not_found",
                query=cleaned,
                message=f"No se encontraron candidatos para {cleaned!r}.",
            )
        return SearchProductsOutcome(
            status="semantic_candidates",
            query=cleaned,
            candidates=tuple(_candidate_from_product(item) for item in candidates),
            message="Candidatos internos recuperados desde el catalogo sintetico.",
        )

    def get_stock_by_branches(
        self,
        *,
        sku: str,
        requested_branch_id: str,
        evaluated_at: str,
        requested_quantity: Decimal | None = None,
    ) -> StockByBranches:
        return self._get_stock_by_branches.execute(
            GetStockByBranchesQuery(
                sku=sku,
                requested_branch_id=requested_branch_id,
                evaluated_at=evaluated_at,
                requested_quantity=requested_quantity,
            )
        )

    def create_quote_draft(
        self,
        *,
        tenant_id: str,
        request_id: str,
        lines: Sequence[DraftLineRequest],
        discount_requested: bool = False,
    ) -> CreateQuoteResult:
        return self._create_quote_draft.execute(
            CreateQuoteDraftCommand(
                tenant_id=tenant_id,
                request_id=request_id,
                lines=tuple(lines),
                discount_requested=discount_requested,
            )
        )

    def expects_contextual_reply(self, conversation_id: str | None) -> bool:
        if not conversation_id:
            return False
        state = self._sessions.get(conversation_id.strip())
        return state is not None and any(
            (
                state.deferred_location_query,
                state.pending_selection,
                state.pending_quantity,
                state.awaiting_reopen_choice,
            )
        )

    def format_verified_context(
        self,
        user_message: str,
        *,
        conversation_id: str | None = None,
    ) -> str | None:
        prepared = self.prepare_customer_turn(user_message, conversation_id=conversation_id)
        return None if prepared is None else prepared.verified_context

    def prepare_customer_turn(
        self,
        user_message: str,
        *,
        conversation_id: str | None = None,
    ) -> PreparedCustomerTurn | None:
        message = " ".join(user_message.split())
        if not message or _normalize_words(message) in {"hola", "buenas", "buenos dias"}:
            return None
        conversation_key = conversation_id.strip() if conversation_id else None
        if conversation_key is None:
            return self._prepare_without_session(message)

        state = self._session(conversation_key)
        now = self._clock()
        inactivity = None if state.last_activity is None else now - state.last_activity
        state.last_activity = now

        reopened = self._handle_reopen_choice(state, message)
        if reopened is not None:
            message = reopened
        elif state.awaiting_reopen_choice:
            return self._prepared(
                state,
                "[HERMES_SESSION:reopen_choice_required]",
                "¿Quieres continuar con la cotización anterior o comenzar una nueva?",
            )
        elif state.finalized_draft:
            state.awaiting_reopen_choice = True
            state.deferred_reopen_query = message
            return self._prepared(
                state,
                "[HERMES_SESSION:finalized_draft_followup]",
                "¿Quieres agregarlo a la cotización anterior o comenzar una nueva?",
            )
        elif inactivity is not None and state.cart:
            if inactivity > _START_NEW_AFTER:
                self._clear_commercial_state(state)
            elif inactivity >= _ASK_TO_RESUME_AFTER:
                state.awaiting_reopen_choice = True
                state.deferred_reopen_query = message
                return self._prepared(
                    state,
                    "[HERMES_SESSION:inactive_quote_followup]",
                    "¿Quieres continuar con la cotización anterior o comenzar una nueva?",
                )

        if state.deferred_location_query is not None:
            original_query = state.deferred_location_query
            state.deferred_location_query = None
            state.location_name = message
            state.branch_id = _branch_for_location(message)
            prepared = self._process_commercial_message(state, original_query)
            return _prefix_customer_reply(
                prepared,
                f"Gracias, tomaré {message} como ubicación para esta cotización.",
            )
        if state.location_name is None:
            state.deferred_location_query = message
            return self._prepared(
                state,
                "[HERMES_SESSION:location_required]",
                "Antes de comenzar, ¿desde qué ciudad o zona nos escribes?",
            )
        return self._process_commercial_message(state, message)

    def _prepare_without_session(self, message: str) -> PreparedCustomerTurn:
        outcome = self.search_products(message, limit=3)
        if outcome.status == "exact_match":
            candidate = outcome.candidates[0]
            return PreparedCustomerTurn(
                _format_candidate(candidate),
                (
                    f"Encontré {candidate.name} a ${_format_money(candidate.unit_price)} "
                    f"por {candidate.unit}. ¿Qué cantidad necesitas?"
                ),
            )
        if outcome.status == "semantic_candidates":
            pending = PendingProductSelection(message, outcome.candidates, None, "sede-norte")
            return self._format_confirmation_request(pending)
        return self._format_non_match(outcome, ())

    def _process_commercial_message(
        self,
        state: ConversationState,
        message: str,
    ) -> PreparedCustomerTurn:
        normalized = _normalize_words(message)
        if _declines_recommendations(normalized):
            state.recommendations_declined = True
            return self._prepared(
                state,
                "[HERMES_SESSION:recommendations_declined]",
                "Entendido, no te mostraré más recomendaciones en esta cotización.",
            )
        if _requests_cart(normalized):
            return self._format_cart(state)
        if _requests_finish(normalized):
            return self._finalize_cart(state)
        if _requests_remove(normalized):
            return self._remove_cart_line(state, message)
        if _requests_quantity_change(normalized):
            return self._change_cart_quantity(state, message)

        if state.pending_quantity is not None:
            quantity = _extract_requested_quantity(message)
            if quantity is not None:
                candidate = state.pending_quantity
                state.pending_quantity = None
                return self._add_to_cart(state, candidate, quantity)
            new_outcome = self.search_products(message, limit=3)
            if new_outcome.status in {"exact_match", "semantic_candidates"}:
                state.pending_quantity = None
                return self._handle_search_outcome(state, message, new_outcome)
            return self._prepared(
                state,
                _format_candidate(state.pending_quantity),
                f"¿Cuántos {state.pending_quantity.unit}s necesitas?",
            )

        if state.pending_selection is not None:
            pending = state.pending_selection
            confirmed = _find_confirmed_candidate(message, pending.candidates)
            if confirmed is not None:
                state.pending_selection = None
                quantity = _extract_requested_quantity(message) or pending.requested_quantity
                return self._resolve_candidate(state, confirmed, quantity)
            new_outcome = self.search_products(message, limit=3)
            if new_outcome.status in {"exact_match", "semantic_candidates"}:
                state.pending_selection = None
                return self._handle_search_outcome(state, message, new_outcome)
            return self._format_confirmation_request(pending, state=state)

        outcome = self.search_products(message, limit=3)
        return self._handle_search_outcome(state, message, outcome)

    def _handle_search_outcome(
        self,
        state: ConversationState,
        message: str,
        outcome: SearchProductsOutcome,
    ) -> PreparedCustomerTurn:
        quantity = _extract_requested_quantity(message)
        if outcome.status == "exact_match":
            return self._resolve_candidate(state, outcome.candidates[0], quantity)
        if outcome.status == "semantic_candidates":
            if len(outcome.candidates) == 1:
                return self._resolve_candidate(state, outcome.candidates[0], quantity)
            pending = PendingProductSelection(
                message,
                outcome.candidates,
                quantity,
                state.branch_id or "ubicacion-sin-configurar",
            )
            state.pending_selection = pending
            return self._format_confirmation_request(pending, state=state)
        return self._format_non_match(
            outcome, tuple(line.product.name for line in state.cart.values())
        )

    def _resolve_candidate(
        self,
        state: ConversationState,
        candidate: CandidateProductInfo,
        quantity: Decimal | None,
    ) -> PreparedCustomerTurn:
        if quantity is None:
            state.pending_quantity = candidate
            return self._prepared(
                state,
                _format_candidate(candidate),
                (
                    f"Tenemos {candidate.name} a ${_format_money(candidate.unit_price)} "
                    f"por {candidate.unit}. ¿Cuántos {candidate.unit}s necesitas?"
                ),
            )
        return self._add_to_cart(state, candidate, quantity)

    def _add_to_cart(
        self,
        state: ConversationState,
        candidate: CandidateProductInfo,
        quantity: Decimal,
    ) -> PreparedCustomerTurn:
        existing = state.cart.get(candidate.sku)
        total_quantity = quantity if existing is None else existing.quantity + quantity
        state.cart[candidate.sku] = ConversationCartLine(candidate, total_quantity)
        state.finalized_draft = False
        stock_context = ""
        stock_reply = ""
        try:
            stock = self.get_stock_by_branches(
                sku=candidate.sku,
                requested_branch_id=state.branch_id or "ubicacion-sin-configurar",
                evaluated_at="2026-10-08T15:00:00+00:00",
                requested_quantity=total_quantity,
            )
            stock_context = _format_stock_context(stock)
            stock_reply = _format_stock_for_customer(stock, candidate, state.location_name)
        except Exception:
            stock_reply = " No pude confirmar disponibilidad en este momento."
        action = "Actualicé" if existing is not None else "Agregué"
        reply = (
            f"{action} {_format_quantity(total_quantity)} "
            f"{_display_unit(candidate.unit, total_quantity)} de {candidate.name} "
            f"a ${_format_money(candidate.unit_price)} por {candidate.unit}."
            f"{stock_reply} ¿Necesitas otro producto o quieres ver lo que llevas?"
        )
        return self._prepared(
            state,
            f"{_format_candidate(candidate)}\n{stock_context}\n[HERMES_CART:line_added]",
            reply,
        )

    def _format_confirmation_request(
        self,
        pending: PendingProductSelection,
        *,
        state: ConversationState | None = None,
    ) -> PreparedCustomerTurn:
        context_lines = ["[HERMES_TOOL:search_products status=semantic_candidates]"]
        customer_lines = ["Encontré estas opciones:"]
        for position, candidate in enumerate(pending.candidates, start=1):
            context_lines.append(_format_candidate(candidate))
            customer_lines.append(
                f"{position}. {candidate.name}{_candidate_detail(candidate)}, "
                f"${_format_money(candidate.unit_price)} por {candidate.unit}."
            )
        context_lines.append("[HERMES_GUARD:confirmation_required]")
        customer_lines.append("¿Cuál necesitas?")
        context = "\n".join(context_lines)
        reply = "\n".join(customer_lines)
        return (
            PreparedCustomerTurn(context, reply)
            if state is None
            else self._prepared(state, context, reply)
        )

    def _format_cart(self, state: ConversationState) -> PreparedCustomerTurn:
        if not state.cart:
            return self._prepared(
                state,
                "[HERMES_CART:empty]",
                "Todavía no has agregado productos. ¿Qué necesitas cotizar?",
            )
        lines = ["Esto es lo que llevas:"]
        total = Decimal("0")
        for position, line in enumerate(state.cart.values(), start=1):
            line_total = Decimal(line.product.unit_price) * line.quantity
            total += line_total
            lines.append(
                f"{position}. {_format_quantity(line.quantity)} "
                f"{_display_unit(line.product.unit, line.quantity)} de {line.product.name}: "
                f"${_format_money(str(line_total))}"
            )
        lines.append(f"Total provisional: ${_format_money(str(total))}.")
        lines.append("¿Quieres añadir algo más o finalizar la cotización?")
        return self._prepared(state, "[HERMES_CART:summary]", "\n".join(lines))

    def _finalize_cart(self, state: ConversationState) -> PreparedCustomerTurn:
        if not state.cart:
            return self._prepared(
                state,
                "[HERMES_CART:empty_finalize]",
                "Aún no hay productos en la cotización. ¿Qué necesitas agregar?",
            )
        try:
            result = self.create_quote_draft(
                tenant_id="whatsapp",
                request_id=f"wa-{uuid.uuid4().hex[:12]}",
                lines=tuple(
                    DraftLineRequest(query=line.product.sku, quantity=line.quantity)
                    for line in state.cart.values()
                ),
            )
        except Exception:
            return self._prepared(
                state,
                "[HERMES_CART:draft_failed]",
                "No pude preparar el borrador en este momento. ¿Quieres revisar el carrito?",
            )
        if not isinstance(result, QuoteDraftReady):
            return self._prepared(
                state,
                "[HERMES_CART:draft_rejected]",
                "No pude preparar el borrador con esos datos. ¿Quieres revisar el carrito?",
            )
        state.finalized_draft = True
        quote = result.quote
        noun = "producto" if len(quote.lines) == 1 else "productos"
        return self._prepared(
            state,
            (
                f"[HERMES_TOOL:create_quote_draft quote_id={quote.id} "
                f"status={quote.status.value} lines={len(quote.lines)}]"
            ),
            (
                f"Listo, preparé un borrador con {len(quote.lines)} {noun} por un total de "
                f"${_format_money(str(quote.total.amount))}. "
                "No reserva inventario ni está aprobado."
            ),
        )

    def _remove_cart_line(self, state: ConversationState, message: str) -> PreparedCustomerTurn:
        line = _find_cart_line(message, state.cart)
        if line is None:
            return self._prepared(
                state,
                "[HERMES_CART:remove_ambiguous]",
                "¿Qué producto quieres quitar de la cotización?",
            )
        state.cart.pop(line.product.sku, None)
        state.finalized_draft = False
        return self._prepared(
            state,
            f"[HERMES_CART:line_removed sku={line.product.sku}]",
            f"Listo, quité {line.product.name} de la cotización.",
        )

    def _change_cart_quantity(
        self,
        state: ConversationState,
        message: str,
    ) -> PreparedCustomerTurn:
        line = _find_cart_line(message, state.cart)
        quantity = _extract_requested_quantity(message)
        if line is None or quantity is None:
            return self._prepared(
                state,
                "[HERMES_CART:quantity_change_ambiguous]",
                "¿Qué producto y qué nueva cantidad quieres dejar?",
            )
        state.cart[line.product.sku] = ConversationCartLine(line.product, quantity)
        state.finalized_draft = False
        return self._prepared(
            state,
            f"[HERMES_CART:quantity_changed sku={line.product.sku}]",
            (
                f"Listo, dejé {_format_quantity(quantity)} "
                f"{_display_unit(line.product.unit, quantity)} de {line.product.name}."
            ),
        )

    def _handle_reopen_choice(self, state: ConversationState, message: str) -> str | None:
        if not state.awaiting_reopen_choice:
            return None
        normalized = _normalize_words(message)
        if _chooses_previous_quote(normalized):
            state.awaiting_reopen_choice = False
            state.finalized_draft = False
            deferred = state.deferred_reopen_query
            state.deferred_reopen_query = None
            return deferred or "ver cotizacion"
        if _chooses_new_quote(normalized):
            deferred = state.deferred_reopen_query
            self._clear_commercial_state(state)
            state.deferred_reopen_query = None
            return deferred or ""
        return None

    def _session(self, key: str) -> ConversationState:
        state = self._sessions.get(key)
        if state is None:
            state = ConversationState()
            self._sessions[key] = state
        self._sessions.move_to_end(key)
        while len(self._sessions) > _MAX_CONVERSATIONS:
            self._sessions.popitem(last=False)
        return state

    @staticmethod
    def _clear_commercial_state(state: ConversationState) -> None:
        state.pending_selection = None
        state.pending_quantity = None
        state.cart.clear()
        state.awaiting_reopen_choice = False
        state.finalized_draft = False
        state.recommendations_declined = False

    @staticmethod
    def _prepared(
        state: ConversationState,
        context: str,
        customer_reply: str,
    ) -> PreparedCustomerTurn:
        cart_context = ", ".join(
            f"{line.product.sku}:{_format_quantity(line.quantity)}" for line in state.cart.values()
        )
        session_context = (
            f"[HERMES_SESSION location={state.location_name!r} "
            f"branch={state.branch_id!r} cart={cart_context!r}]"
        )
        return PreparedCustomerTurn(f"{context}\n{session_context}", customer_reply)

    @staticmethod
    def _format_non_match(
        outcome: SearchProductsOutcome,
        cart_names: tuple[str, ...],
    ) -> PreparedCustomerTurn:
        if outcome.status == "catalog_unavailable":
            reply = (
                "En este momento no puedo consultar el catálogo. Prefiero no confirmar "
                "disponibilidad sin información confiable."
            )
        elif outcome.status == "clarification_required":
            reply = "Para ubicar el producto correcto, ¿para qué lo vas a usar?"
        elif cart_names:
            reply = (
                "No encuentro ese producto en el catálogo disponible. "
                f"Podemos continuar con {', '.join(cart_names)}."
            )
        else:
            reply = "No encuentro ese producto en el catálogo disponible. Disculpa."
        return PreparedCustomerTurn(
            f"[HERMES_TOOL:search_products status={outcome.status}] {outcome.message}",
            reply,
        )


_QTY_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:unidades|unidad|unds|und|tubos|bultos|rollos|"
    r"metros|m|laminas|láminas|cajas|pares|galones|libras|kilogramos|kg)\b",
    re.IGNORECASE,
)
_LEADING_QTY_RE = re.compile(
    r"(?:cotizar|cotizame|cotízame|necesito|quiero|dame|deja|pon)\s+"
    r"(\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)


def _candidate_from_product(product: Product) -> CandidateProductInfo:
    return CandidateProductInfo(
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        unit_price=str(product.list_price.amount),
        currency=product.list_price.currency,
        specs=product.specs_dict,
        source=product.source,
        catalog_version=product.catalog_version,
    )


def _extract_requested_quantity(text: str) -> Decimal | None:
    stripped = text.strip()
    match = _QTY_RE.search(stripped) or _LEADING_QTY_RE.search(stripped)
    raw = match.group(1) if match is not None else None
    if raw is None and re.fullmatch(r"\d+(?:[.,]\d+)?", stripped):
        raw = stripped
    if raw is None:
        return None
    try:
        value = Decimal(raw.replace(",", "."))
    except Exception:
        return None
    return value if value > Decimal("0") else None


def _format_candidate(candidate: CandidateProductInfo) -> str:
    specs_text = ", ".join(f"{key}={value}" for key, value in candidate.specs.items())
    return (
        f"[HERMES_PRODUCT sku={candidate.sku} name={candidate.name!r} unit={candidate.unit!r} "
        f"price={candidate.unit_price} currency={candidate.currency} specs={{{specs_text}}}]"
    )


def _candidate_detail(candidate: CandidateProductInfo) -> str:
    preferred = ("calibre", "largo_m", "diametro", "peso_kg", "tipo")
    details = [
        f"{key.replace('_', ' ')} {candidate.specs[key]}"
        for key in preferred
        if key in candidate.specs
    ]
    return " — " + ", ".join(details[:2]) if details else ""


def _find_confirmed_candidate(
    text: str,
    candidates: tuple[CandidateProductInfo, ...],
) -> CandidateProductInfo | None:
    normalized = _normalize_words(text)
    if normalized in {"esa", "ese", "esa misma", "ese mismo", "la ultima", "el ultimo"}:
        return candidates[-1] if candidates else None
    ordinal_matches = (
        (("primero", "primera", "opcion 1"), 0),
        (("segundo", "segunda", "opcion 2"), 1),
        (("tercero", "tercera", "opcion 3"), 2),
    )
    if normalized in {"1", "2", "3"}:
        index = int(normalized) - 1
        return candidates[index] if index < len(candidates) else None
    for phrases, index in ordinal_matches:
        if index < len(candidates) and any(_contains_phrase(normalized, item) for item in phrases):
            return candidates[index]
    message_tokens = set(normalized.split())
    scored: list[tuple[int, CandidateProductInfo]] = []
    for candidate in candidates:
        if candidate.sku.casefold() in text.casefold():
            return candidate
        candidate_tokens = set(_normalize_words(candidate.name).split()) - {"de", "la", "el"}
        score = len(message_tokens & candidate_tokens)
        if score >= 2:
            scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def _branch_for_location(text: str) -> str:
    normalized = _normalize_words(text)
    for term, branch in _KNOWN_BRANCHES.items():
        if term in normalized.split():
            return branch
    slug = "-".join(normalized.split())[:48] or "sin-configurar"
    return f"ubicacion-{slug}"


def _looks_vague(text: str) -> bool:
    words = set(_normalize_words(text).split())
    vague = {"algo", "coso", "cosa", "pieza", "eso"}
    filler = {"el", "la", "del", "de", "para", "un", "una", "necesito", "quiero"}
    meaningful = words - vague - filler
    return bool(words & vague) and len(meaningful) < 2


def _normalize_words(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _format_money(value: str) -> str:
    amount = Decimal(value)
    whole, _, decimals = f"{amount:.2f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    return grouped if decimals == "00" else f"{grouped},{decimals}"


def _format_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _format_stock_context(stock: StockByBranches) -> str:
    status = (
        stock.fulfillment_status.value if stock.fulfillment_status is not None else "unrequested"
    )
    return (
        f"[HERMES_STOCK sku={stock.sku} branch={stock.requested_branch_id} "
        f"local={stock.local_available} shortfall={stock.shortfall} status={status}]"
    )


def _format_stock_for_customer(
    stock: StockByBranches,
    candidate: CandidateProductInfo,
    location_name: str | None,
) -> str:
    location = location_name or stock.requested_branch_id.replace("sede-", "sede ")
    if stock.fulfillment_status is not None and stock.fulfillment_status.value == "sufficient":
        return f" Hay disponibilidad confirmada para esa cantidad en {location}."
    alternatives = tuple(item for item in stock.alternatives if item.is_firm and item.quantity > 0)
    if alternatives:
        names = ", ".join(item.origin_name for item in alternatives[:2])
        return (
            f" No tengo disponibilidad confirmada para toda la cantidad en {location}, "
            f"pero aparece una alternativa en {names}."
        )
    local = next((item for item in stock.items if item.kind.value == "local"), None)
    if local is not None and local.is_firm and local.quantity > 0:
        return (
            f" En {location} aparecen {_format_quantity(local.quantity)} "
            f"{_display_unit(candidate.unit, local.quantity)} disponibles."
        )
    return f" No tengo disponibilidad confirmada en {location}; disculpa."


def _display_unit(unit: str, quantity: Decimal) -> str:
    if quantity == Decimal("1"):
        return unit
    irregular = {
        "unidad": "unidades",
        "metro": "metros",
        "lamina": "laminas",
        "par": "pares",
        "galon": "galones",
        "kilogramo": "kilogramos",
    }
    return irregular.get(unit, unit if unit.endswith("s") else f"{unit}s")


def _prefix_customer_reply(prepared: PreparedCustomerTurn, prefix: str) -> PreparedCustomerTurn:
    return PreparedCustomerTurn(prepared.verified_context, f"{prefix} {prepared.customer_reply}")


def _requests_cart(text: str) -> bool:
    return any(
        phrase in text for phrase in ("que llevo", "ver carrito", "ver cotizacion", "resumen")
    )


def _requests_finish(text: str) -> bool:
    return any(
        phrase in text
        for phrase in ("finalizar", "terminar", "cotizame eso", "cotiza eso", "eso es todo")
    )


def _requests_remove(text: str) -> bool:
    return any(word in text.split() for word in ("quita", "quitar", "elimina", "eliminar"))


def _requests_quantity_change(text: str) -> bool:
    return any(word in text.split() for word in ("cambia", "cambiar", "deja", "pon"))


def _declines_recommendations(text: str) -> bool:
    return any(
        phrase in text
        for phrase in ("no recomiendes", "sin recomendaciones", "no insistas", "solo eso")
    )


def _chooses_previous_quote(text: str) -> bool:
    return any(phrase in text for phrase in ("anterior", "misma", "continuar", "agregarla"))


def _chooses_new_quote(text: str) -> bool:
    return any(phrase in text for phrase in ("nueva", "nuevo pedido", "empezar de nuevo"))


def _find_cart_line(
    text: str,
    cart: dict[str, ConversationCartLine],
) -> ConversationCartLine | None:
    message_tokens = set(_normalize_words(text).split())
    scored: list[tuple[int, ConversationCartLine]] = []
    for line in cart.values():
        product_tokens = set(_normalize_words(line.product.name).split()) - {"de", "la", "el"}
        score = len(message_tokens & product_tokens)
        if score:
            scored.append((score, line))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    return scored[0][1]
