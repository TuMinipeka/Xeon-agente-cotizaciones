from __future__ import annotations

import hashlib
import logging
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from xeon.agent.tool_trace import record_tool
from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.ports.conversation_memory import PendingCandidates, ResolvedLine
from xeon.application.quote_draft import (
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    CreateQuoteResult,
    DiscountPolicyUnavailable,
    DraftLineRequest,
    IdempotencyConflict,
    QuoteDraftReady,
)
from xeon.application.quote_request import classify_line_query
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery, StockByBranches
from xeon.domain.quote import Quote

_LOG = logging.getLogger(__name__)


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


class CommercialToolbelt:
    """Authorized commercial tools exposed to the XEON agent.

    Combines hybrid catalog discovery (exact SKU/alias + semantic RAG context + JSONB specs)
    with deterministic database queries for prices, stock, and quote drafts.
    """

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

    def search_products(self, query: str, *, limit: int = 3) -> SearchProductsOutcome:
        outcome = self._search_products(query, limit=limit)
        self._record_search(outcome)
        return outcome

    def evaluated_at(self) -> str:
        return self._clock().astimezone(UTC).isoformat()

    @staticmethod
    def _record_search(outcome: SearchProductsOutcome) -> None:
        record_tool(
            "search_products",
            status=outcome.status,
            sku=outcome.candidates[0].sku if outcome.candidates else "none",
        )

    def _search_products(self, query: str, *, limit: int = 3) -> SearchProductsOutcome:
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
        if re.search(r"\b(?:coso|cosa)\b", cleaned, re.IGNORECASE):
            return SearchProductsOutcome(
                status="clarification_required",
                query=cleaned,
                clarification_reason="ambiguous_reference",
                message=(
                    "La referencia es ambigua; se necesitan caracteristicas "
                    "antes de seleccionar un SKU."
                ),
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
            if classified.reason == "ambiguous_reference":
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
        try:
            result = self._get_stock_by_branches.execute(
                GetStockByBranchesQuery(
                    sku=sku,
                    requested_branch_id=requested_branch_id,
                    evaluated_at=evaluated_at,
                    requested_quantity=requested_quantity,
                )
            )
        except Exception:
            record_tool("get_stock_by_branches", status="unavailable")
            raise
        local = next(
            (item for item in result.items if item.branch_id == result.requested_branch_id),
            None,
        )
        record_tool(
            "get_stock_by_branches",
            sku=result.sku,
            sede=result.requested_branch_id
            if result.requested_branch_id.startswith("sede-")
            else "unknown",
            disponible=str(result.local_available)
            if result.local_available is not None
            else "unknown",
            vigencia=local.freshness.value if local is not None else "unknown",
        )
        return result

    def create_quote_draft(
        self,
        *,
        tenant_id: str,
        request_id: str,
        lines: Sequence[DraftLineRequest],
        discount_requested: bool = False,
        version: int = 1,
    ) -> CreateQuoteResult:
        try:
            result = self._create_quote_draft.execute(
                CreateQuoteDraftCommand(
                    tenant_id=tenant_id,
                    request_id=request_id,
                    lines=tuple(lines),
                    discount_requested=discount_requested,
                    version=version,
                )
            )
        except Exception:
            record_tool("create_quote_draft", status="unavailable")
            raise
        if isinstance(result, QuoteDraftReady):
            record_tool(
                "create_quote_draft",
                quote_id=str(result.quote.id),
                lineas=len(result.quote.lines),
                subtotal=f"{result.quote.subtotal.amount} {result.quote.currency}",
                replayed=str(result.replayed).lower(),
            )
        else:
            record_tool("create_quote_draft", status=type(result).__name__)
        return result

    def prepare_verified_context(
        self,
        user_message: str,
        *,
        request_id: str | None = None,
        conversation_key: str | None = None,
        last_sku: str | None = None,
        pending: PendingCandidates | None = None,
        known_lines: tuple[ResolvedLine, ...] = (),
        fallback_quantity: Decimal | None = None,
    ) -> tuple[str | None, str | None, PendingCandidates | None, tuple[ResolvedLine, ...]]:
        normalized = user_message.strip()
        if not normalized or normalized.casefold() in {"hola", "buenas", "buenos dias"}:
            return None, None, None, ()

        discount_requested = _requests_discount(normalized)
        if _requests_quote_summary(normalized) and known_lines:
            try:
                summary = self.create_quote_draft(
                    tenant_id="whatsapp",
                    request_id=_draft_request_id(
                        conversation_key,
                        tuple(DraftLineRequest(line.sku, line.quantity) for line in known_lines),
                        request_id,
                    ),
                    lines=tuple(DraftLineRequest(line.sku, line.quantity) for line in known_lines),
                    discount_requested=discount_requested,
                )
                if isinstance(summary, QuoteDraftReady):
                    return _format_draft(summary.quote), last_sku, None, ()
                if isinstance(summary, DiscountPolicyUnavailable):
                    return (
                        "[XEON_TOOL:create_quote_draft status=discount_policy_unavailable] "
                        "No hay politica de descuentos aprobada; no se creo un borrador.",
                        last_sku,
                        None,
                        (),
                    )
            except Exception as exc:
                _LOG.error("Quote draft source unavailable: %s", type(exc).__name__)
                return (
                    "[XEON_TOOL:create_quote_draft status=quote_unavailable] "
                    "No fue posible crear el borrador; intenta mas tarde.",
                    last_sku,
                    None,
                    (),
                )

        branch = _extract_requested_branch(normalized)
        selection = _pending_selection(normalized, pending)
        clauses: tuple[tuple[str, Decimal | None], ...]
        if selection is not None and pending is not None:
            clauses = (
                (
                    selection,
                    _extract_requested_quantity(normalized)
                    or pending.quantity
                    or fallback_quantity,
                ),
            )
            branch = pending.branch if not _has_branch(normalized) else branch
        else:
            clauses = tuple(
                (part.strip(), _extract_requested_quantity(part))
                for part in re.split(
                    r"(?:\s+(?:y|mas)\s+|,\s+|;\s*)(?=\d+(?:[.,]\d+)?\s+)",
                    normalized,
                    flags=re.I,
                )
            )

        contexts: list[str] = []
        draft_lines: list[DraftLineRequest] = []
        resolved: list[ResolvedLine] = []
        selected_sku: str | None = None
        for clause, quantity in clauses:
            exact_query = _explicit_product_query(clause)
            outcome = self._search_products(exact_query or clause, limit=3)
            if exact_query is not None and outcome.status == "semantic_candidates":
                outcome = self._search_products(clause, limit=3)
            if last_sku is not None and outcome.status in {"not_found", "clarification_required"}:
                outcome = self._search_products(last_sku, limit=1)
            self._record_search(outcome)
            if outcome.status in {"clarification_required", "catalog_unavailable", "not_found"}:
                return (
                    f"[XEON_TOOL:search_products status={outcome.status}] {outcome.message}",
                    None,
                    None,
                    (),
                )
            if outcome.status == "semantic_candidates" and len(outcome.candidates) > 1:
                options = "\n".join(
                    f"- SKU={candidate.sku} | opcion={index} | nombre={candidate.name} "
                    f"| precio_bd={candidate.unit_price} {candidate.currency}"
                    for index, candidate in enumerate(outcome.candidates, start=1)
                )
                return (
                    "[XEON_TOOL:search_products status=clarification_required] "
                    "Hay varias referencias posibles. Pregunta cual opcion desea el cliente; "
                    "no crees borrador antes de su eleccion.\n"
                    + options
                    + "\n¿Cual opcion eliges (1, 2 o 3)?",
                    None,
                    PendingCandidates(
                        tuple(item.sku for item in outcome.candidates),
                        tuple(item.name for item in outcome.candidates),
                        quantity or fallback_quantity,
                        branch,
                    ),
                    (),
                )
            primary = outcome.candidates[0]
            selected_sku = primary.sku
            if quantity is None:
                quantity = next(
                    (line.quantity for line in known_lines if line.sku == primary.sku), None
                )
            if quantity is None and pending is not None and primary.sku in pending.skus:
                quantity = pending.quantity or fallback_quantity
            if quantity is None and _requests_quote(normalized) and outcome.status == "exact_match":
                quantity = fallback_quantity
            contexts.append(f"[XEON_TOOL:search_products status={outcome.status}]")
            contexts.append(
                f"- SKU={primary.sku} | nombre={primary.name} | unidad={primary.unit} "
                f"| precio_bd={primary.unit_price} {primary.currency}"
            )
            try:
                stock = self.get_stock_by_branches(
                    sku=primary.sku,
                    requested_branch_id=branch,
                    evaluated_at=self._clock().astimezone(UTC).isoformat(),
                    requested_quantity=quantity,
                )
                stock_status = (
                    stock.fulfillment_status.value if stock.fulfillment_status else "unrequested"
                )
                contexts.append(
                    f"[XEON_TOOL:get_stock_by_branches sku={stock.sku} "
                    f"sede_solicitada={stock.requested_branch_id} "
                    f"disponible_local={stock.local_available} "
                    f"faltante={stock.shortfall} "
                    f"estado={stock_status}]"
                )
                for item in stock.items:
                    contexts.append(
                        f"- sede={item.branch_id} ({item.origin_name}) | "
                        f"cantidad={item.quantity} | tipo={item.kind.value} "
                        f"| vigencia={item.freshness.value}"
                    )
            except Exception as exc:
                _LOG.error("Stock source unavailable: %s", type(exc).__name__)
                contexts.append(
                    "[XEON_TOOL:get_stock_by_branches status=stock_unavailable] "
                    "La fuente de inventario no esta disponible; existencia desconocida."
                )
            if quantity is not None:
                draft_lines.append(DraftLineRequest(query=primary.sku, quantity=quantity))
                resolved.append(ResolvedLine(primary.sku, quantity))

        if draft_lines and len(draft_lines) == len(clauses):
            try:
                result = self.create_quote_draft(
                    tenant_id="whatsapp",
                    request_id=_draft_request_id(conversation_key, tuple(draft_lines), request_id),
                    lines=tuple(draft_lines),
                    discount_requested=discount_requested,
                )
                if isinstance(result, QuoteDraftReady):
                    contexts.append(_format_draft(result.quote))
                elif isinstance(result, DiscountPolicyUnavailable):
                    contexts.append(
                        "[XEON_TOOL:create_quote_draft status=discount_policy_unavailable] "
                        "No hay politica de descuentos aprobada; no se creo un borrador."
                    )
                elif isinstance(result, IdempotencyConflict):
                    contexts.append(
                        "[XEON_TOOL:create_quote_draft status=idempotency_conflict] "
                        "El identificador de solicitud ya tiene otras lineas."
                    )
            except Exception as exc:
                _LOG.error("Quote draft source unavailable: %s", type(exc).__name__)
                contexts.append(
                    "[XEON_TOOL:create_quote_draft status=quote_unavailable] "
                    "No fue posible crear el borrador; intenta mas tarde."
                )
        return "\n".join(contexts), selected_sku, None, tuple(resolved)


_QTY_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:unidades|unidad|unds|und|tubos|bultos|rollos|metros|m)\b",
    re.IGNORECASE,
)
_LEADING_QTY_RE = re.compile(
    r"(?:cotizar|cotizame|necesito|quiero|dame)\s+(\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)
_DISCOUNT_RE = re.compile(
    r"\b(?:descuentos?|rebajas?|rebajame|barato|precio\s+especial)\b|"
    r"\b\d+(?:[.,]\d+)?\s*(?:%|por\s+ciento)(?!\w)",
    re.IGNORECASE,
)
_QUOTE_SUMMARY_RE = re.compile(r"\b(?:precio\s+de\s+lista|a\s+lista|total|borrador)\b", re.I)
_QUOTE_REQUEST_RE = re.compile(r"\b(?:cotiza|cotizame|cotizacion|borrador|pedido)\b", re.I)


def _format_draft(quote: Quote) -> str:
    header = (
        f"[XEON_TOOL:create_quote_draft quote_id={quote.id} "
        f"status={quote.status.value} version=v{quote.version} "
        f"sku={quote.lines[0].sku} cantidad={quote.lines[0].quantity} "
        f"subtotal={quote.subtotal.amount} {quote.currency} "
        f"total={quote.total.amount} {quote.currency} lines={len(quote.lines)}]"
    )
    details = [
        f"- SKU={line.sku} nombre={line.description} cantidad={line.quantity} "
        f"unidad={line.unit} precio_bd={line.unit_price.amount} {quote.currency} "
        f"subtotal_linea={line.line_total.amount} {quote.currency}"
        for line in quote.lines
    ]
    return "\n".join((header, *details))


def _draft_request_id(
    conversation_key: str | None,
    lines: tuple[DraftLineRequest, ...],
    fallback_request_id: str | None,
) -> str:
    if conversation_key is None:
        return fallback_request_id or f"wa-{uuid.uuid4().hex[:12]}"
    signature = "\n".join(
        f"{line.query}\t{Decimal(str(line.quantity)).normalize()}"
        for line in sorted(lines, key=lambda line: (line.query, Decimal(str(line.quantity))))
    )
    digest = hashlib.sha256(f"{conversation_key}\n{signature}".encode()).hexdigest()[:32]
    return f"xeon-{digest}"


def _requests_quote_summary(text: str) -> bool:
    return _QUOTE_SUMMARY_RE.search(text) is not None


def _requests_quote(text: str) -> bool:
    return _QUOTE_REQUEST_RE.search(text) is not None


def _has_branch(text: str) -> bool:
    return re.search(r"\b(?:sede\s+)?(?:norte|sur|centro)\b", text, re.I) is not None


def _pending_selection(text: str, pending: PendingCandidates | None) -> str | None:
    if pending is None:
        return None
    match = re.search(r"^\s*([1-3])\s*$|\bopcion\s+([1-3])\b|\bel\s+([1-3])\b", text, re.I)
    if match is not None:
        index = int(match.group(1) or match.group(2) or match.group(3)) - 1
    elif re.search(r"\b(?:el|la)\s+primer[oa]\b", text, re.I):
        index = 0
    elif re.search(r"\b(?:el|la)\s+segund[oa]\b", text, re.I):
        index = 1
    elif re.search(r"\b(?:el|la)\s+tercer[oa]\b", text, re.I):
        index = 2
    else:
        index = -1
    if 0 <= index < len(pending.skus):
        return pending.skus[index]
    direct = next(
        (
            sku
            for sku, name in zip(pending.skus, pending.names, strict=True)
            if sku.casefold() in text.casefold() or name.casefold() in text.casefold()
        ),
        None,
    )
    if direct is not None:
        return direct
    tokens = set(re.findall(r"[a-z0-9]+", text.casefold())) - {"con", "de", "la", "el", "mango"}
    if not tokens:
        return None
    scores = []
    for position, (sku, name) in enumerate(zip(pending.skus, pending.names, strict=True)):
        specs = pending.attributes[position] if position < len(pending.attributes) else {}
        candidate_tokens = set(
            re.findall(r"[a-z0-9]+", (name + " " + " ".join(specs.values())).casefold())
        )
        scores.append((len(tokens & candidate_tokens), sku))
    best = max(score for score, _ in scores)
    winners = [sku for score, sku in scores if score == best and score > 0]
    return winners[0] if len(winners) == 1 else None


def _explicit_product_query(clause: str) -> str | None:
    sku = re.search(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b", clause, re.I)
    if sku is not None:
        return sku.group()
    if re.search(r"\btubos?\b", clause, re.I) and "1/2" in clause:
        return "tubo 1/2"
    if re.search(r"\bcemento\b", clause, re.I) and re.search(r"\b50\s*kg\b", clause, re.I):
        return "cemento 50kg"
    without_logistics = re.split(
        r"\s+y\s+(?:entrega|recogida|retiro|lo recojo|lo retiro)\b",
        clause,
        maxsplit=1,
        flags=re.I,
    )[0]
    match = re.search(
        r"\b\d+(?:[.,]\d+)?\s+(?:bultos?|tubos?|rollos?|metros?|unidades?|laminas?)"
        r"\s+(?:de\s+)?(.+)$",
        without_logistics,
        re.I,
    )
    if match is None:
        return None
    product = re.split(
        r"\s+(?:disponibles?\b|en\s+(?:la\s+)?sede|para\s+(?:entrega|recogida))\b",
        match.group(1),
        maxsplit=1,
        flags=re.I,
    )[0].strip(" .,?!")
    product = re.sub(r"\s+por\s+favor$", "", product, flags=re.I)
    return product


def _requests_discount(text: str) -> bool:
    return _DISCOUNT_RE.search(text) is not None


def _extract_requested_quantity(text: str) -> Decimal | None:
    match = _QTY_RE.search(text) or _LEADING_QTY_RE.search(text)
    if match is None:
        return None
    raw = match.group(1)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    else:
        raw = raw.replace(",", ".")
    try:
        value = Decimal(raw)
    except Exception:
        return None
    return value if value > Decimal("0") else None


def _extract_requested_branch(text: str) -> str:
    if re.search(r"\b(?:sede\s+)?sur\b", text, re.IGNORECASE):
        return "sede-sur"
    if re.search(r"\b(?:sede\s+)?centro\b", text, re.IGNORECASE):
        return "sede-centro"
    return "sede-norte"
