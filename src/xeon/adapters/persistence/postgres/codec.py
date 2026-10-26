"""Versioned, explicit JSON representations; never pickle untrusted state."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from xeon.application.ports.funnel import FunnelState
from xeon.application.reply import Option, Reply
from xeon.domain.cart import CartLine, QuoteCart
from xeon.domain.money import Money
from xeon.domain.product import Product, ProductId
from xeon.domain.quote import Quote, QuoteLine, QuoteStatus

SCHEMA_VERSION = 1


def _check(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Version de estado persistido no compatible.")
    return cast(dict[str, Any], payload["data"])


def _wrap(data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "data": data}


def product_out(product: Product) -> dict[str, Any]:
    return {
        "sku": product.sku,
        "name": product.name,
        "unit": product.unit,
        "amount": str(product.list_price.amount),
        "currency": product.list_price.currency,
        "aliases": list(product.aliases),
        "source": product.source,
        "catalog_version": product.catalog_version,
        "specs": [list(x) for x in product.specs],
        "description_context": product.description_context,
    }


def product_in(data: dict[str, Any]) -> Product:
    return Product(
        id=ProductId(data["sku"]),
        name=data["name"],
        unit=data["unit"],
        list_price=Money(Decimal(data["amount"]), data["currency"]),
        aliases=tuple(data["aliases"]),
        source=data["source"],
        catalog_version=data["catalog_version"],
        specs=tuple((str(pair[0]), str(pair[1])) for pair in data["specs"]),
        description_context=data["description_context"],
    )


def cart_out(cart: QuoteCart) -> dict[str, Any]:
    return _wrap(
        {
            "conversation_key": cart.conversation_key,
            "version": cart.version,
            "quote_version": cart.quote_version,
            "last_request_id": cart.last_request_id,
            "lines": [
                {
                    "label": line.label,
                    "quantity": str(line.quantity),
                    "product": product_out(line.product) if line.product else None,
                }
                for line in cart.lines
            ],
        }
    )


def cart_in(payload: dict[str, Any]) -> QuoteCart:
    data = _check(payload)
    return QuoteCart(
        conversation_key=data["conversation_key"],
        version=data["version"],
        quote_version=data["quote_version"],
        last_request_id=data["last_request_id"],
        lines=tuple(
            CartLine(
                label=line["label"],
                quantity=Decimal(line["quantity"]),
                product=product_in(line["product"]) if line["product"] else None,
            )
            for line in data["lines"]
        ),
    )


def reply_out(reply: Reply) -> dict[str, Any]:
    return {
        "text": reply.text,
        "kind": reply.kind,
        "step": reply.step,
        "options": [asdict(option) for option in reply.options],
    }


def reply_in(data: dict[str, Any]) -> Reply:
    return Reply(
        text=data["text"],
        kind=data["kind"],
        step=data["step"],
        options=tuple(Option(**item) for item in data["options"]),
    )


def funnel_out(state: FunnelState) -> dict[str, Any]:
    data = asdict(state)
    data["last_reply"] = reply_out(state.last_reply) if state.last_reply else None
    return _wrap(data)


def funnel_in(payload: dict[str, Any]) -> FunnelState:
    data = _check(payload).copy()
    data["candidates"] = tuple(data["candidates"])
    if data["last_reply"]:
        data["last_reply"] = reply_in(data["last_reply"])
    return FunnelState(**data)


def quote_out(quote: Quote) -> dict[str, Any]:
    return _wrap(
        {
            "id": str(quote.id),
            "tenant_id": quote.tenant_id,
            "request_id": quote.request_id,
            "version": quote.version,
            "status": quote.status.value,
            "currency": quote.currency,
            "catalog_version": quote.catalog_version,
            "source": quote.source,
            "notes": quote.notes,
            "subtotal": str(quote.subtotal.amount),
            "total": str(quote.total.amount),
            "lines": [
                {
                    "product_id": line.product_id,
                    "sku": line.sku,
                    "description": line.description,
                    "unit": line.unit,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price.amount),
                    "line_total": str(line.line_total.amount),
                    "catalog_version": line.catalog_version,
                    "source": line.source,
                }
                for line in quote.lines
            ],
        }
    )


def quote_in(payload: dict[str, Any]) -> Quote:
    data = _check(payload)
    currency = data["currency"]
    return Quote(
        id=UUID(data["id"]),
        tenant_id=data["tenant_id"],
        request_id=data["request_id"],
        version=data["version"],
        status=QuoteStatus(data["status"]),
        currency=currency,
        lines=tuple(
            QuoteLine(
                product_id=line["product_id"],
                sku=line["sku"],
                description=line["description"],
                unit=line["unit"],
                quantity=Decimal(line["quantity"]),
                unit_price=Money(Decimal(line["unit_price"]), currency),
                line_total=Money(Decimal(line["line_total"]), currency),
                catalog_version=line["catalog_version"],
                source=line["source"],
            )
            for line in data["lines"]
        ),
        subtotal=Money(Decimal(data["subtotal"]), currency),
        total=Money(Decimal(data["total"]), currency),
        catalog_version=data["catalog_version"],
        source=data["source"],
        notes=data["notes"],
    )
