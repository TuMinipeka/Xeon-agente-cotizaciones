from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from xeon.agent.tool_trace import record_tool
from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.ports.conversation_memory import PendingCandidates
from xeon.application.quote_draft import (
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    CreateQuoteResult,
    DraftLineRequest,
    QuoteDraftReady,
)
from xeon.application.quote_request import classify_line_query
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery, StockByBranches
from xeon.domain.quote import Quote


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

    Combines lexical catalog discovery with deterministic prices, stock, and drafts.
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

            candidates = self._catalog.search_candidates(cleaned, limit=max(limit, 20))
            if re.search(r"\btubos?\s+pvc\b", cleaned, re.I):
                candidates = tuple(
                    item for item in candidates if item.name.casefold().startswith("tubo pvc")
                )
            elif re.search(r"\bpalas?\b", cleaned, re.I):
                candidates = tuple(
                    item for item in candidates if item.name.casefold().startswith("pala")
                )
            candidates = candidates[:limit]
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
                "Candidatos recuperados por busqueda lexical y atributos tecnicos (specs). "
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
            sede=result.requested_branch_id,
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
    tokens = set(re.findall(r"[a-z]{3,}", text.casefold())) - {
        "con",
        "del",
        "las",
        "los",
        "mango",
        "bultos",
        "unidades",
    }
    if not tokens:
        return None
    candidate_terms: list[set[str]] = []
    for position, (_sku, name) in enumerate(zip(pending.skus, pending.names, strict=True)):
        specs = pending.attributes[position] if position < len(pending.attributes) else {}
        candidate_terms.append(
            set(re.findall(r"[a-z]{3,}", (name + " " + " ".join(specs.values())).casefold()))
        )
    scores = []
    for position, (terms, sku) in enumerate(zip(candidate_terms, pending.skus, strict=True)):
        shared = set().union(
            *(other for index, other in enumerate(candidate_terms) if index != position)
        )
        scores.append((len(tokens & (terms - shared)), sku))
    best = max(score for score, _ in scores)
    winners = [sku for score, sku in scores if score == best and score > 0]
    return winners[0] if len(winners) == 1 else None


def _explicit_product_query(clause: str) -> str | None:
    sku = re.search(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b", clause, re.I)
    if sku is not None:
        return sku.group()
    if re.search(r"\btubos?\b", clause, re.I) and "1/2" in clause:
        return "tubo 1/2"
    if re.search(r"\btubos?\s+pvc\b", clause, re.I):
        return "tubos pvc"
    if re.search(r"\bcemento\b", clause, re.I) and re.search(r"\b50\s*kg\b", clause, re.I):
        return "cemento 50kg"
    trailing_quantity = re.search(
        r"^\s*(.+?)\s+\d+(?:[.,]\d+)?\s+(?:bultos?|unidades?|palas?)\s*$",
        clause,
        re.I,
    )
    if trailing_quantity is not None:
        return trailing_quantity.group(1).strip()
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
    if re.match(r"(?i)^(?:en\s+(?:la\s+)?sede|disponibles?\b)", product):
        return None
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
