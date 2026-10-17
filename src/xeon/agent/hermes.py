from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from xeon.application.ports.catalog import CatalogUnavailableError, ProductCatalog
from xeon.application.quote_draft import (
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    CreateQuoteResult,
    DraftLineRequest,
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

    def format_verified_context(self, user_message: str) -> str | None:
        normalized = user_message.strip()
        if not normalized or normalized.casefold() in {"hola", "buenas", "buenos dias"}:
            return None

        outcome = self.search_products(normalized, limit=3)
        if outcome.status in {"exact_match", "semantic_candidates"}:
            lines = [f"[HERMES_TOOL:search_products status={outcome.status}]"]
            for candidate in outcome.candidates:
                specs_text = ", ".join(f"{k}={v}" for k, v in candidate.specs.items())
                lines.append(
                    f"- SKU={candidate.sku} | nombre={candidate.name} | unidad={candidate.unit} "
                    f"| precio_bd={candidate.unit_price} {candidate.currency} "
                    f"| specs={{{specs_text}}}"
                )
            lines.append(outcome.message)
            return "\n".join(lines)

        if outcome.status in {"clarification_required", "catalog_unavailable"}:
            return f"[HERMES_TOOL:search_products status={outcome.status}] {outcome.message}"

        return None
