from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    conversation_id: UUID = Field(default_factory=uuid4)


class ChatResponse(BaseModel):
    conversation_id: UUID
    reply: str
    provider: str
    model: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    provider: str
    model: str


class QuoteLineIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(gt=0)


class CreateQuoteDraftRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=80)
    request_id: str = Field(min_length=1, max_length=80)
    lines: tuple[QuoteLineIn, ...] = Field(min_length=1)
    discount_requested: bool = False


class QuoteLineOut(BaseModel):
    sku: str
    description: str
    unit: str
    quantity: Decimal
    unit_price: str
    line_total: str
    catalog_version: str
    source: str


class QuoteDraftOut(BaseModel):
    id: UUID
    tenant_id: str
    request_id: str
    version: int
    status: Literal["DRAFT"]
    currency: str
    subtotal: str
    total: str
    catalog_version: str
    source: str
    notes: str
    lines: tuple[QuoteLineOut, ...]
    replayed: bool = False


class AvailabilityItemOut(BaseModel):
    sku: str
    branch_id: str | None
    origin_id: str
    origin_name: str
    quantity: Decimal
    kind: Literal["local", "transfer", "delivery"]
    channel: Literal["on_hand", "delivery"]
    source: str
    observed_at: str


class StockByBranchesOut(BaseModel):
    sku: str
    requested_branch_id: str
    items: tuple[AvailabilityItemOut, ...]


class QuoteOutcomeResponse(BaseModel):
    outcome: Literal[
        "draft_ready",
        "clarification_required",
        "product_not_found",
        "catalog_unavailable",
        "discount_policy_unavailable",
    ]
    message: str | None = None
    query: str | None = None
    reason: str | None = None
    quote: QuoteDraftOut | None = None
