from __future__ import annotations

import re
import unicodedata
import uuid
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
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


_MAX_PENDING_SELECTIONS = 1024


class HermesToolbelt:
    """Authorized commercial tools exposed to the Hermes orchestrator.

    Combines hybrid catalog discovery (exact SKU/alias + semantic RAG context + JSONB specs)
    with deterministic database queries for prices, stock, and quote drafts.
    """

    def __init__(
        self,
        *,
        catalog: ProductCatalog,
        create_quote_draft: CreateQuoteDraft,
        get_stock_by_branches: GetStockByBranches,
    ) -> None:
        self._catalog = catalog
        self._create_quote_draft = create_quote_draft
        self._get_stock_by_branches = get_stock_by_branches
        self._pending_selections: OrderedDict[str, PendingProductSelection] = OrderedDict()
        self._mentioned_products: OrderedDict[str, tuple[str, ...]] = OrderedDict()

    def search_products(self, query: str, *, limit: int = 3) -> SearchProductsOutcome:
        cleaned = query.strip()
        if not cleaned:
            return SearchProductsOutcome(
                status="clarification_required",
                query=query,
                clarification_reason="empty_query",
                message="Se requiere una descripcion o SKU para buscar en el catalogo.",
            )

        classified = classify_line_query(cleaned)
        if classified.reason == "missing_units":
            return SearchProductsOutcome(
                status="clarification_required",
                query=cleaned,
                clarification_reason="missing_units",
                message="Faltan unidades y contexto; esas medidas no determinan una referencia.",
            )

        try:
            exact = self._catalog.find_exact(cleaned)
            if exact is not None:
                return SearchProductsOutcome(
                    status="exact_match",
                    query=cleaned,
                    candidates=(
                        CandidateProductInfo(
                            sku=exact.sku,
                            name=exact.name,
                            unit=exact.unit,
                            unit_price=str(exact.list_price.amount),
                            currency=exact.list_price.currency,
                            specs=exact.specs_dict,
                            source=exact.source,
                            catalog_version=exact.catalog_version,
                        ),
                    ),
                    message=f"Coincidencia exacta para {exact.sku}.",
                )

            candidates = self._catalog.search_candidates(cleaned, limit=limit)
        except CatalogUnavailableError:
            return SearchProductsOutcome(
                status="catalog_unavailable",
                query=cleaned,
                message=(
                    "El catalogo no esta disponible; desconocido o fuente caida "
                    "no significa agotado."
                ),
            )

        if not candidates:
            if classified.reason == "ambiguous_reference" and _looks_vague(cleaned):
                return SearchProductsOutcome(
                    status="clarification_required",
                    query=cleaned,
                    clarification_reason="ambiguous_reference",
                    message=(
                        "La referencia es ambigua; se necesitan caracteristicas "
                        "antes de seleccionar un SKU."
                    ),
                )
            return SearchProductsOutcome(
                status="not_found",
                query=cleaned,
                message=(
                    f"No se encontraron candidatos para {cleaned!r}; "
                    "desconocido no significa existencia cero."
                ),
            )

        return SearchProductsOutcome(
            status="semantic_candidates",
            query=cleaned,
            candidates=tuple(
                CandidateProductInfo(
                    sku=item.sku,
                    name=item.name,
                    unit=item.unit,
                    unit_price=str(item.list_price.amount),
                    currency=item.list_price.currency,
                    specs=item.specs_dict,
                    source=item.source,
                    catalog_version=item.catalog_version,
                )
                for item in candidates
            ),
            message=(
                "Candidatos recuperados por contexto semantico (RAG) y atributos tecnicos (specs). "
                "Confirma la referencia con el comprador antes de cerrar linea."
            ),
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
        normalized = user_message.strip()
        if not normalized or normalized.casefold() in {"hola", "buenas", "buenos dias"}:
            return None

        conversation_key = conversation_id.strip() if conversation_id else None
        pending = (
            self._pending_selections.get(conversation_key) if conversation_key is not None else None
        )
        if pending is not None:
            confirmed = _find_confirmed_candidate(normalized, pending.candidates)
            if confirmed is None:
                return self._format_confirmation_request(pending)

            assert conversation_key is not None
            self._pending_selections.pop(conversation_key, None)
            quantity = _extract_requested_quantity(normalized) or pending.requested_quantity
            branch_id = _extract_requested_branch(
                normalized,
                default=pending.requested_branch_id,
            )
            return self._format_resolved_product(
                confirmed,
                status="confirmed_selection",
                message=(
                    f"El comprador confirmo explicitamente el SKU {confirmed.sku}; "
                    "ya se permiten consultas comerciales para esa referencia."
                ),
                quantity=quantity,
                branch_id=branch_id,
                conversation_key=conversation_key,
            )

        outcome = self.search_products(normalized, limit=3)
        if outcome.status == "semantic_candidates":
            pending = PendingProductSelection(
                query=normalized,
                candidates=outcome.candidates,
                requested_quantity=_extract_requested_quantity(normalized),
                requested_branch_id=_extract_requested_branch(normalized),
            )
            if conversation_key is not None:
                self._pending_selections[conversation_key] = pending
                self._pending_selections.move_to_end(conversation_key)
                while len(self._pending_selections) > _MAX_PENDING_SELECTIONS:
                    self._pending_selections.popitem(last=False)
            return self._format_confirmation_request(pending)

        if outcome.status == "exact_match":
            return self._format_resolved_product(
                outcome.candidates[0],
                status=outcome.status,
                message=outcome.message,
                quantity=_extract_requested_quantity(normalized),
                branch_id=_extract_requested_branch(normalized),
                conversation_key=conversation_key,
            )

        if outcome.status in {"clarification_required", "catalog_unavailable"}:
            customer_reply = (
                "Necesito un poco más de información para encontrar el producto correcto. "
                "Cuéntame para qué lo vas a usar y, si mencionas medidas, incluye las unidades."
                if outcome.status == "clarification_required"
                else (
                    "En este momento no puedo consultar el catálogo. Prefiero no confirmar "
                    "existencias hasta tener información confiable. ¿Necesitas algo más?"
                )
            )
            return PreparedCustomerTurn(
                verified_context=(
                    f"[HERMES_TOOL:search_products status={outcome.status}] {outcome.message}"
                ),
                customer_reply=customer_reply,
            )

        if outcome.status == "not_found":
            mentioned = (
                self._mentioned_products.get(conversation_key, ())
                if conversation_key is not None
                else ()
            )
            if mentioned:
                products = ", ".join(mentioned)
                customer_reply = (
                    "Por ahora no encuentro ese producto en el catálogo disponible. "
                    f"Puedo continuar con lo que ya revisamos: {products}. ¿Necesitas algo más?"
                )
            else:
                customer_reply = (
                    "Por ahora no encuentro ese producto en el catálogo disponible. "
                    "¿Quieres que revisemos otra opción de ferretería?"
                )
            return PreparedCustomerTurn(
                verified_context=(
                    f"[HERMES_TOOL:search_products status=not_found] {outcome.message}"
                ),
                customer_reply=customer_reply,
            )

        return None

    @staticmethod
    def _format_confirmation_request(
        pending: PendingProductSelection,
    ) -> PreparedCustomerTurn:
        lines = ["[HERMES_TOOL:search_products status=semantic_candidates]"]
        for candidate in pending.candidates:
            lines.append(_format_candidate(candidate))
        lines.append(
            "[HERMES_GUARD:confirmation_required] Los resultados son solo candidatos. "
            "Pide al comprador que responda con uno de los SKU mostrados. Hasta entonces no "
            "consultes stock ni crees un borrador."
        )
        customer_lines = ["Encontré estas opciones:"]
        for position, candidate in enumerate(pending.candidates, start=1):
            customer_lines.append(
                f"{position}. {candidate.name}, por {candidate.unit}, "
                f"a ${_format_money(candidate.unit_price)} {candidate.currency}."
            )
        customer_lines.append(
            "¿Cuál necesitas? Puedes responder con el nombre o con el número de la opción."
        )
        return PreparedCustomerTurn(
            verified_context="\n".join(lines),
            customer_reply="\n".join(customer_lines),
        )

    def _format_resolved_product(
        self,
        candidate: CandidateProductInfo,
        *,
        status: str,
        message: str,
        quantity: Decimal | None,
        branch_id: str,
        conversation_key: str | None,
    ) -> PreparedCustomerTurn:
        lines = [f"[HERMES_TOOL:search_products status={status}]", _format_candidate(candidate)]
        lines.append(message)
        customer_lines = [
            f"Perfecto, revisaré {candidate.name}. El precio disponible es "
            f"${_format_money(candidate.unit_price)} {candidate.currency} por {candidate.unit}."
        ]
        stock: StockByBranches | None = None

        try:
            stock = self.get_stock_by_branches(
                sku=candidate.sku,
                requested_branch_id=branch_id,
                evaluated_at="2026-10-08T15:00:00+00:00",
                requested_quantity=quantity,
            )
            status_val = (
                stock.fulfillment_status.value
                if stock.fulfillment_status is not None
                else "unrequested"
            )
            lines.append(
                f"[HERMES_TOOL:get_stock_by_branches sku={stock.sku} "
                f"sede_solicitada={stock.requested_branch_id} "
                f"disponible_local={stock.local_available} "
                f"faltante={stock.shortfall} "
                f"estado={status_val}]"
            )
            for item in stock.items:
                lines.append(
                    f"- sede={item.branch_id} ({item.origin_name}) | "
                    f"cantidad={item.quantity} | tipo={item.kind.value} | "
                    f"vigencia={item.freshness.value}"
                )
        except Exception:
            customer_lines.append(
                "No pude confirmar la disponibilidad en este momento, así que no te diré que "
                "está agotado sin verificarlo."
            )

        if stock is not None:
            customer_lines.append(_format_stock_for_customer(stock, candidate))

        if quantity is not None:
            try:
                draft_res = self.create_quote_draft(
                    tenant_id="whatsapp",
                    request_id=f"wa-{uuid.uuid4().hex[:12]}",
                    lines=(DraftLineRequest(query=candidate.sku, quantity=quantity),),
                )
                if isinstance(draft_res, QuoteDraftReady):
                    quote = draft_res.quote
                    lines.append(
                        f"[HERMES_TOOL:create_quote_draft quote_id={quote.id} "
                        f"status={quote.status.value} version=v{quote.version} "
                        f"sku={candidate.sku} cantidad={quantity} "
                        f"subtotal={quote.subtotal.amount} {quote.currency} "
                        f"total={quote.total.amount} {quote.currency}]"
                    )
                    customer_lines.append(
                        f"Preparé un borrador por {_format_quantity(quantity)} "
                        f"{_display_unit(candidate.unit, quantity)} de {candidate.name}, "
                        "con un total de "
                        f"${_format_money(str(quote.total.amount))} {quote.currency}. "
                        "Es un borrador y no reserva inventario ni representa una aprobación."
                    )
            except Exception:
                customer_lines.append(
                    "No pude preparar el borrador en este momento. ¿Quieres que revisemos la "
                    "cantidad?"
                )
        else:
            customer_lines.append("¿Qué cantidad necesitas?")

        customer_lines.append("¿Necesitas algo más?")
        self._remember_product(conversation_key, candidate.name)
        return PreparedCustomerTurn(
            verified_context="\n".join(lines),
            customer_reply=" ".join(customer_lines),
        )

    def _remember_product(self, conversation_key: str | None, product_name: str) -> None:
        if conversation_key is None:
            return
        existing = self._mentioned_products.get(conversation_key, ())
        if product_name not in existing:
            self._mentioned_products[conversation_key] = (*existing, product_name)
        self._mentioned_products.move_to_end(conversation_key)
        while len(self._mentioned_products) > _MAX_PENDING_SELECTIONS:
            self._mentioned_products.popitem(last=False)


_QTY_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:unidades|unidad|unds|und|tubos|bultos|rollos|metros|m)\b",
    re.IGNORECASE,
)
_LEADING_QTY_RE = re.compile(
    r"(?:cotizar|cotizame|necesito|quiero|dame)\s+(\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)


def _extract_requested_quantity(text: str) -> Decimal | None:
    match = _QTY_RE.search(text) or _LEADING_QTY_RE.search(text)
    if match is None:
        return None
    raw = match.group(1).replace(",", ".")
    try:
        value = Decimal(raw)
    except Exception:
        return None
    return value if value > Decimal("0") else None


def _format_candidate(candidate: CandidateProductInfo) -> str:
    specs_text = ", ".join(f"{key}={value}" for key, value in candidate.specs.items())
    return (
        f"- SKU={candidate.sku} | nombre={candidate.name} | unidad={candidate.unit} "
        f"| precio_bd={candidate.unit_price} {candidate.currency} | specs={{{specs_text}}}"
    )


def _find_confirmed_candidate(
    text: str,
    candidates: tuple[CandidateProductInfo, ...],
) -> CandidateProductInfo | None:
    normalized = _normalize_words(text)
    ordinal_matches = (
        (("1", "primero", "primera", "opcion 1"), 0),
        (("2", "segundo", "segunda", "opcion 2"), 1),
        (("3", "tercero", "tercera", "opcion 3"), 2),
    )
    for phrases, index in ordinal_matches:
        if index < len(candidates) and any(
            _contains_phrase(normalized, phrase) for phrase in phrases
        ):
            return candidates[index]

    for candidate in candidates:
        sku_pattern = rf"(?<![A-Z0-9]){re.escape(candidate.sku)}(?![A-Z0-9])"
        if re.search(sku_pattern, text, re.IGNORECASE):
            return candidate

    message_tokens = set(normalized.split())
    scored: list[tuple[int, CandidateProductInfo]] = []
    for candidate in candidates:
        candidate_tokens = {
            token
            for token in _normalize_words(candidate.name).split()
            if token not in {"de", "del", "la", "el", "por"}
        }
        score = len(message_tokens & candidate_tokens)
        if score >= 2:
            scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def _extract_requested_branch(text: str, *, default: str = "sede-norte") -> str:
    lowered = text.casefold()
    if "sur" in lowered:
        return "sede-sur"
    if "centro" in lowered:
        return "sede-centro"
    if "norte" in lowered:
        return "sede-norte"
    return default


def _looks_vague(text: str) -> bool:
    normalized = _normalize_words(text)
    return any(word in normalized.split() for word in {"algo", "coso", "cosa", "pieza", "eso"})


def _normalize_words(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _format_money(value: str) -> str:
    return f"{Decimal(value):,.2f}"


def _format_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _format_stock_for_customer(
    stock: StockByBranches,
    candidate: CandidateProductInfo,
) -> str:
    branch_name = stock.requested_branch_id.replace("sede-", "sede ")
    if stock.requested_quantity is not None:
        if stock.fulfillment_status is None or stock.fulfillment_status.value == "unknown":
            return (
                f"No puedo confirmar todavía la cantidad disponible en {branch_name}; "
                "la información no está vigente o no está disponible."
            )
        if stock.fulfillment_status.value == "sufficient":
            return (
                f"En {branch_name} hay disponibilidad para las "
                f"{_format_quantity(stock.requested_quantity)} "
                f"{_display_unit(candidate.unit, stock.requested_quantity)} solicitadas."
            )
        return (
            f"En {branch_name} aparecen {_format_quantity(stock.local_available or Decimal('0'))} "
            f"{_display_unit(candidate.unit, stock.local_available or Decimal('0'))} "
            "disponibles y faltan "
            f"{_format_quantity(stock.shortfall or Decimal('0'))}."
        )

    local = next((item for item in stock.items if item.kind.value == "local"), None)
    if local is None or not local.is_firm:
        return f"No puedo confirmar disponibilidad vigente en {branch_name}."
    return (
        f"En {branch_name} aparecen {_format_quantity(local.quantity)} "
        f"{_display_unit(candidate.unit, local.quantity)} disponibles."
    )


def _display_unit(unit: str, quantity: Decimal) -> str:
    if quantity == Decimal("1"):
        return unit
    irregular = {"unidad": "unidades", "metro": "metros"}
    return irregular.get(unit, unit if unit.endswith("s") else f"{unit}s")
