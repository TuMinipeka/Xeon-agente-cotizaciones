"""Build the data of a quote PDF from the quote, the conversation state and the store policy.

Never includes the customer's phone number or any conversation identifier.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from xeon.application.policy_schema import StorePolicy
from xeon.application.ports.funnel import FunnelState
from xeon.application.ports.quote_pdf import PdfLine, QuotePdfDocument
from xeon.domain.quote import STATUS_LABEL_ES, Quote

LEGEND = "Borrador de cotización - no es factura ni reserva de inventario"
PENDING = "pendiente de confirmar con un asesor"
DELIVERY_LABEL = {"recogida": "Recoger en sede", "domicilio": "Domicilio"}


def format_cop(value: Decimal) -> str:
    """Colombian peso style without decimals, from the backend Decimal: $1.234.500."""
    return "$" + f"{value:,.0f}".replace(",", ".")


def quote_number(quote: Quote) -> str:
    return f"COT-{quote.id.hex[:8].upper()}"


def build_quote_pdf_document(
    quote: Quote,
    *,
    state: FunnelState,
    policy: StorePolicy,
    tenant_id: str,
    branch_name: str | None,
    issued_on: date,
) -> QuotePdfDocument:
    details = tuple(
        item
        for item in (
            f"NIT {policy.nit}" if policy.nit else None,
            policy.direccion,
            f"Tel. {policy.telefono_tienda}" if policy.telefono_tienda else None,
        )
        if item
    )
    name = policy.nombre_comercial or (
        f"Ferretería demo ({tenant_id})" if policy.demo else tenant_id
    )
    delivery = DELIVERY_LABEL.get(state.delivery or "", PENDING)
    if state.delivery == "domicilio" and state.address:
        delivery = f"{delivery}: {state.address}"
    validity = (
        f"{policy.vigencia_cotizacion_dias} días desde la emisión"
        if policy.vigencia_cotizacion_dias
        else PENDING
    )
    tax = policy.iva if policy.iva and policy.iva != "pendiente" else PENDING
    return QuotePdfDocument(
        store_name=name,
        store_details=details,
        number=quote_number(quote),
        version=quote.version,
        issued_on=issued_on.isoformat(),
        status_label=STATUS_LABEL_ES[quote.status],
        lines=tuple(
            PdfLine(
                description=line.description,
                quantity=f"{line.quantity.normalize():f} {line.unit}",
                unit_price=format_cop(line.unit_price.amount),
                subtotal=format_cop(line.line_total.amount),
            )
            for line in quote.lines
        ),
        total=format_cop(quote.total.amount),
        currency=quote.currency,
        delivery=delivery,
        branch=branch_name or PENDING,
        payment=state.payment or PENDING,
        validity=validity,
        tax_note=f"IVA: {tax}. El total no incluye impuestos ni descuentos.",
        legend=LEGEND,
    )
