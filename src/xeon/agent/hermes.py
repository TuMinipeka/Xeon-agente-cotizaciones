from __future__ import annotations

import re
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
            )

        if outcome.status in {"clarification_required", "catalog_unavailable"}:
            return f"[HERMES_TOOL:search_products status={outcome.status}] {outcome.message}"

        return None

    @staticmethod
    def _format_confirmation_request(pending: PendingProductSelection) -> str:
        lines = ["[HERMES_TOOL:search_products status=semantic_candidates]"]
        for candidate in pending.candidates:
            lines.append(_format_candidate(candidate))
        lines.append(
            "[HERMES_GUARD:confirmation_required] Los resultados son solo candidatos. "
            "Pide al comprador que responda con uno de los SKU mostrados. Hasta entonces no "
            "consultes stock ni crees un borrador."
        )
        return "\n".join(lines)

    def _format_resolved_product(
        self,
        candidate: CandidateProductInfo,
        *,
        status: str,
        message: str,
        quantity: Decimal | None,
        branch_id: str,
    ) -> str:
        lines = [f"[HERMES_TOOL:search_products status={status}]", _format_candidate(candidate)]
        lines.append(message)

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
            pass

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
            except Exception:
                pass

        return "\n".join(lines)


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
    for candidate in candidates:
        sku_pattern = rf"(?<![A-Z0-9]){re.escape(candidate.sku)}(?![A-Z0-9])"
        if re.search(sku_pattern, text, re.IGNORECASE):
            return candidate
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
