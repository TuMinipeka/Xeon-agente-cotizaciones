from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response

from xeon.adapters.llm.openai_compatible import LLMProviderError
from xeon.api.schemas import (
    AvailabilityItemOut,
    ChatRequest,
    ChatResponse,
    CreateQuoteDraftRequest,
    HealthResponse,
    QuoteDraftOut,
    QuoteLineOut,
    QuoteOutcomeResponse,
    StockByBranchesOut,
)
from xeon.application.container import AppContainer, build_container
from xeon.application.ports.catalog import ProductCatalog
from xeon.application.ports.inventory import BranchInventory
from xeon.application.ports.llm import LLMPort
from xeon.application.ports.quotes import QuoteDraftRepository
from xeon.application.quote_draft import (
    CatalogUnavailable,
    ClarificationRequired,
    CreateQuoteDraftCommand,
    DiscountPolicyUnavailable,
    DraftLineRequest,
    ProductNotFound,
    QuoteDraftReady,
    QuoteNotFoundError,
)
from xeon.application.stock import AvailabilityItem, GetStockByBranchesQuery, StockByBranches
from xeon.config import Settings, get_settings
from xeon.domain.inventory import InvalidInventoryError
from xeon.domain.quote import EmptyQuoteError, InvalidQuantityError, Quote


def _quote_out(quote: Quote, *, replayed: bool = False) -> QuoteDraftOut:
    return QuoteDraftOut(
        id=quote.id,
        tenant_id=quote.tenant_id,
        request_id=quote.request_id,
        version=quote.version,
        status=quote.status.value,
        currency=quote.currency,
        subtotal=str(quote.subtotal.amount),
        total=str(quote.total.amount),
        catalog_version=quote.catalog_version,
        source=quote.source,
        notes=quote.notes,
        replayed=replayed,
        lines=tuple(
            QuoteLineOut(
                sku=line.sku,
                description=line.description,
                unit=line.unit,
                quantity=line.quantity,
                unit_price=str(line.unit_price.amount),
                line_total=str(line.line_total.amount),
                catalog_version=line.catalog_version,
                source=line.source,
            )
            for line in quote.lines
        ),
    )


def _availability_item_out(item: AvailabilityItem) -> AvailabilityItemOut:
    return AvailabilityItemOut(
        sku=item.sku,
        branch_id=item.branch_id,
        origin_id=item.origin_id,
        origin_name=item.origin_name,
        quantity=item.quantity,
        kind=item.kind.value,
        channel=item.channel.value,
        source=item.source,
        observed_at=item.observed_at,
        valid_until=item.valid_until,
        freshness=item.freshness.value,
        is_firm=item.is_firm,
        age=item.age,
    )


def _stock_out(result: StockByBranches) -> StockByBranchesOut:
    return StockByBranchesOut(
        sku=result.sku,
        requested_branch_id=result.requested_branch_id,
        evaluated_at=result.evaluated_at,
        items=tuple(_availability_item_out(item) for item in result.items),
        requested_quantity=result.requested_quantity,
        fulfillment_status=(
            None if result.fulfillment_status is None else result.fulfillment_status.value
        ),
        local_available=result.local_available,
        shortfall=result.shortfall,
        alternatives=tuple(_availability_item_out(item) for item in result.alternatives),
    )


def create_app(
    settings: Settings | None = None,
    llm: LLMPort | None = None,
    catalog: ProductCatalog | None = None,
    inventory: BranchInventory | None = None,
    quotes: QuoteDraftRepository | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    runtime = container or build_container(
        settings or get_settings(),
        catalog=catalog,
        inventory=inventory,
        quotes=quotes,
        llm=llm,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await runtime.aclose()

    application = FastAPI(
        title="XEON API",
        version="0.1.0",
        description=(
            "API local de XEON. El chat interpreta; el cotizador calcula borradores DRAFT. "
            "No emite ni aprueba cotizaciones."
        ),
        lifespan=lifespan,
    )

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            environment=runtime.settings.app_env,
            provider=runtime.settings.llm_provider,
            model=runtime.settings.llm_model,
        )

    @application.post("/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        try:
            result = await runtime.agent.respond(request.message)
        except LLMProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ChatResponse(
            conversation_id=request.conversation_id,
            reply=result.text,
            provider=result.provider,
            model=result.model,
        )

    @application.post("/v1/quotes", response_model=QuoteOutcomeResponse)
    async def create_quote(
        request: CreateQuoteDraftRequest,
        response: Response,
    ) -> QuoteOutcomeResponse:
        try:
            result = runtime.create_quote_draft.execute(
                CreateQuoteDraftCommand(
                    tenant_id=request.tenant_id,
                    request_id=request.request_id,
                    lines=tuple(
                        DraftLineRequest(query=line.query, quantity=line.quantity)
                        for line in request.lines
                    ),
                    discount_requested=request.discount_requested,
                )
            )
        except (EmptyQuoteError, InvalidQuantityError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if isinstance(result, QuoteDraftReady):
            response.status_code = 200 if result.replayed else 201
            return QuoteOutcomeResponse(
                outcome="draft_ready",
                quote=_quote_out(result.quote, replayed=result.replayed),
            )
        if isinstance(result, ClarificationRequired):
            response.status_code = 422
            return QuoteOutcomeResponse(
                outcome="clarification_required",
                query=result.query,
                reason=result.reason,
                message=result.message,
            )
        if isinstance(result, ProductNotFound):
            response.status_code = 422
            return QuoteOutcomeResponse(
                outcome="product_not_found",
                query=result.query,
                message=result.message,
            )
        if isinstance(result, CatalogUnavailable):
            response.status_code = 503
            return QuoteOutcomeResponse(outcome="catalog_unavailable", message=result.message)
        if isinstance(result, DiscountPolicyUnavailable):
            response.status_code = 422
            return QuoteOutcomeResponse(
                outcome="discount_policy_unavailable",
                message=result.message,
            )
        raise HTTPException(status_code=500, detail="Resultado comercial no reconocido.")

    @application.get("/v1/stock", response_model=StockByBranchesOut)
    async def get_stock(
        sku: str = Query(min_length=1, max_length=80),
        requested_branch_id: str = Query(min_length=1, max_length=80),
        evaluated_at: str = Query(min_length=1, max_length=40),
        requested_quantity: Annotated[Decimal | None, Query(gt=0)] = None,
    ) -> StockByBranchesOut:
        try:
            result = runtime.get_stock_by_branches.execute(
                GetStockByBranchesQuery(
                    sku=sku,
                    requested_branch_id=requested_branch_id,
                    evaluated_at=evaluated_at,
                    requested_quantity=requested_quantity,
                )
            )
        except InvalidInventoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _stock_out(result)

    @application.get("/v1/quotes/{quote_id}", response_model=QuoteDraftOut)
    async def get_quote(
        quote_id: UUID,
        tenant_id: str = Query(min_length=1, max_length=80),
    ) -> QuoteDraftOut:
        try:
            quote = runtime.get_quote_draft.execute(quote_id, tenant_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Borrador no encontrado.") from exc
        return _quote_out(quote)

    return application


app = create_app()
