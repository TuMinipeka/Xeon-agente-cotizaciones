from decimal import Decimal
from uuid import uuid4

import pytest

from xeon.domain.money import Money
from xeon.domain.product import Product, ProductId
from xeon.domain.quote import (
    INITIAL_QUOTE_VERSION,
    InvalidQuoteError,
    InvalidQuoteLineError,
    Quote,
    QuoteLine,
    QuoteStatus,
    build_draft_quote,
    build_quote_line,
)


def _product() -> Product:
    return Product(
        id=ProductId("CEM-50"),
        name="Cemento gris 50 kg",
        unit="bulto",
        list_price=Money("28900.00", "COP"),
        aliases=("cemento",),
        source="synthetic-ferreteria-demo-xeon",
        catalog_version="synthetic-2026-10-08",
    )


def test_quote_line_rejects_inconsistent_total() -> None:
    with pytest.raises(InvalidQuoteLineError, match="precio por cantidad"):
        QuoteLine(
            product_id="CEM-50",
            sku="CEM-50",
            description="Cemento gris 50 kg",
            unit="bulto",
            quantity=Decimal("2"),
            unit_price=Money("28900.00", "COP"),
            line_total=Money("1.00", "COP"),
            catalog_version="synthetic-2026-10-08",
            source="synthetic-ferreteria-demo-xeon",
        )


def test_draft_quote_starts_at_version_one() -> None:
    line = build_quote_line(_product(), 2)
    quote = build_draft_quote((line,), tenant_id="demo", request_id="req-1")

    assert quote.status is QuoteStatus.DRAFT
    assert quote.version == INITIAL_QUOTE_VERSION
    assert quote.total == quote.subtotal == Money("57800.00", "COP")


def test_quote_rejects_total_different_from_subtotal() -> None:
    line = build_quote_line(_product(), 1)
    with pytest.raises(InvalidQuoteError, match="total y subtotal"):
        Quote(
            id=uuid4(),
            tenant_id="demo",
            request_id="req-1",
            version=1,
            status=QuoteStatus.DRAFT,
            currency="COP",
            lines=(line,),
            subtotal=line.line_total,
            total=Money("1.00", "COP"),
            catalog_version=line.catalog_version,
            source=line.source,
            notes="Datos sinteticos de Ferreteria Demo XEON. No atribuir a una empresa real.",
        )
