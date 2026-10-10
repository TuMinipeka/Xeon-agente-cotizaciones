from __future__ import annotations

import re
from dataclasses import dataclass

from xeon.application.find_product import FindProduct, ProductFound
from xeon.application.quote_draft import (
    CatalogUnavailable,
    ClarificationRequired,
    CreateQuoteDraft,
    CreateQuoteDraftCommand,
    CreateQuoteResult,
    DiscountPolicyUnavailable,
    DraftLineRequest,
    ProductNotFound,
    QuoteDraftReady,
)
from xeon.application.stock import GetStockByBranches, GetStockByBranchesQuery, StockByBranches
from xeon.domain.quote import EmptyQuoteError, InvalidQuantityError, Quote

SYNTHETIC_CHAT_EVALUATED_AT = "2026-10-08T15:00:00+00:00"
DEFAULT_CHAT_BRANCH_ID = "sede-norte"
DEFAULT_CHAT_TENANT_ID = "demo"

_LEADING_VERB = re.compile(r"(?i)^(necesito|quiero|cotiza(?:r)?|dame)\s+")
_PART_SPLIT = re.compile(r"(?i)\s+y\s+|,\s*")
_QUANTIFIED_LINE = re.compile(
    r"(?i)(\d+(?:[.,]\d+)?)\s*(?:bultos?|metros?|unidades?|kg)?\s*(?:de\s+)?(.+)"
)


def extract_requested_lines(message: str) -> tuple[DraftLineRequest, ...]:
    text = _LEADING_VERB.sub("", message.strip())
    if not text:
        return ()
    lines: list[DraftLineRequest] = []
    for part in _PART_SPLIT.split(text):
        match = _QUANTIFIED_LINE.search(part.strip())
        if match is None:
            continue
        quantity = match.group(1).replace(",", ".")
        query = match.group(2).strip()
        if query:
            lines.append(DraftLineRequest(query=query, quantity=quantity))
    return tuple(lines)


@dataclass(frozen=True, slots=True)
class CommercialTurnResult:
    tools_used: tuple[str, ...]
    outcome: str
    reply: str
    quote_result: CreateQuoteResult | None = None
    quote: Quote | None = None
    stock: StockByBranches | None = None


class CommercialTurn:
    def __init__(
        self,
        find_product: FindProduct,
        get_stock: GetStockByBranches,
        create_quote_draft: CreateQuoteDraft,
    ) -> None:
        self._find_product = find_product
        self._get_stock = get_stock
        self._create_quote_draft = create_quote_draft

    def execute(
        self,
        message: str,
        *,
        tenant_id: str,
        request_id: str,
        requested_branch_id: str,
        evaluated_at: str,
    ) -> CommercialTurnResult:
        lines = extract_requested_lines(message)
        if not lines:
            return CommercialTurnResult(
                tools_used=(),
                outcome="no_commercial_request",
                reply="",
            )

        for line in lines:
            found = self._find_product.execute(line.query)
            if isinstance(found, ProductFound):
                continue
            if isinstance(found, ClarificationRequired):
                return CommercialTurnResult(
                    tools_used=("find_product",),
                    outcome="clarification_required",
                    reply=found.message,
                    quote_result=found,
                )
            if isinstance(found, ProductNotFound):
                return CommercialTurnResult(
                    tools_used=("find_product",),
                    outcome="product_not_found",
                    reply=found.message,
                    quote_result=found,
                )
            return CommercialTurnResult(
                tools_used=("find_product",),
                outcome="catalog_unavailable",
                reply=found.message,
                quote_result=found,
            )

        first_sku = self._find_product.execute(lines[0].query)
        stock: StockByBranches | None = None
        if isinstance(first_sku, ProductFound):
            stock = self._get_stock.execute(
                GetStockByBranchesQuery(
                    sku=first_sku.product.sku,
                    requested_branch_id=requested_branch_id,
                    evaluated_at=evaluated_at,
                    requested_quantity=lines[0].quantity,
                )
            )

        try:
            quote_result = self._create_quote_draft.execute(
                CreateQuoteDraftCommand(
                    tenant_id=tenant_id,
                    request_id=request_id,
                    lines=lines,
                    discount_requested="descuento" in message.casefold(),
                )
            )
        except (EmptyQuoteError, InvalidQuantityError) as exc:
            return CommercialTurnResult(
                tools_used=("find_product", "consult_stock"),
                outcome="invalid_request",
                reply=str(exc),
                stock=stock,
            )

        tools_used = ("find_product", "consult_stock", "create_draft")
        if isinstance(quote_result, QuoteDraftReady):
            return CommercialTurnResult(
                tools_used=tools_used,
                outcome="draft_ready",
                reply=_draft_reply(quote_result, stock),
                quote_result=quote_result,
                quote=quote_result.quote,
                stock=stock,
            )
        if isinstance(quote_result, DiscountPolicyUnavailable):
            return CommercialTurnResult(
                tools_used=tools_used,
                outcome="discount_policy_unavailable",
                reply=quote_result.message,
                quote_result=quote_result,
                stock=stock,
            )
        if isinstance(quote_result, CatalogUnavailable):
            return CommercialTurnResult(
                tools_used=("find_product", "consult_stock"),
                outcome="catalog_unavailable",
                reply=quote_result.message,
                quote_result=quote_result,
                stock=stock,
            )
        return CommercialTurnResult(
            tools_used=("find_product",),
            outcome="clarification_required",
            reply=quote_result.message,
            quote_result=quote_result,
            stock=stock,
        )


def _draft_reply(result: QuoteDraftReady, stock: StockByBranches | None) -> str:
    quote = result.quote
    line = quote.lines[0]
    stock_text = ""
    if stock is not None and stock.fulfillment_status is not None:
        local = "desconocido" if stock.local_available is None else str(stock.local_available)
        shortfall = "desconocido" if stock.shortfall is None else str(stock.shortfall)
        stock_text = (
            f" Stock en {stock.requested_branch_id}: cumplimiento"
            f" {stock.fulfillment_status.value}, local {local}, faltante {shortfall}."
        )
    return (
        f"Encontre {line.sku} {line.description}."
        f"{stock_text} Borrador DRAFT {quote.id} version {quote.version},"
        f" total {quote.total.amount} {quote.currency}. No esta aprobado ni emitido."
        " Los precios los calculo el backend con datos sinteticos."
    )
